import asyncio
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import os
import random
from time import time, sleep
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor
import logging

from src.core.http import HTTP

# Create logs folder if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging (log errors/warnings only to file and console)
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scraper.log"),
        logging.StreamHandler()
    ]
)

os.makedirs("output", exist_ok=True)
college_list = []

def generate_careers360_url(page):
    base_url = "https://www.careers360.com/colleges/india-colleges-fctp"
    query_params = {
        "page": page,
        "degree": "64,2,72,14,6,65,100,101,150,75,168,9,211",
        "sort_by": "3"
    }
    encoded_params = urllib.parse.urlencode(query_params, safe=",")
    return f"{base_url}?{encoded_params}"

async def fetch_main_page(http, page):
    url = generate_careers360_url(page)
    try:
        response = await http.get(url)
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        logging.error(f"Error fetching page {page}: {e}")
        return None

def parse_main_page(soup):
    if soup is None:
        return []

    local_colleges = []
    colleges = soup.find_all("div", class_="card_block")

    for college in colleges:
        college_soup = BeautifulSoup(str(college), 'html.parser')

        college_data = {
            "College Name": college_soup.find("h3", class_="college_name").text.strip() if college_soup.find("h3", class_="college_name") else "N/A",
            "Location": college_soup.find("span", class_="location").text.strip() if college_soup.find("span", class_="location") else "N/A",
            "Fees": college_soup.find("li", string=lambda s: "Fees :" in s if s else False).text.replace("Fees :", "").strip() if college_soup.find("li", string=lambda s: "Fees :" in s if s else False) else "N/A",
            "Rating": college_soup.find("span", class_="star_text").text.strip() if college_soup.find("span", class_="star_text") else "N/A",
            "Reviews": college_soup.find("span", class_="review_text").text.strip() if college_soup.find("span", class_="review_text") else "N/A",
            "NIRF Ranking": college_soup.find("div", class_="ranking_strip").text.strip() if college_soup.find("div", class_="ranking_strip") else "N/A",
            "College URL": college_soup.find('a', class_='general_text')['href'] if college_soup.find('a', class_='general_text') else "N/A"
        }

        local_colleges.append(college_data)

    return local_colleges

async def scrape_main_pages(start_page, end_page, save_interval=5):
    global college_list
    async with httpx.AsyncClient(timeout=30) as client:
        http = HTTP(client, max_concurrency=5)

        tasks = [fetch_main_page(http, page) for page in range(start_page, end_page + 1)]
        results = await asyncio.gather(*tasks)

        for i, soup in enumerate(results, start=start_page):
            college_list.extend(parse_main_page(soup))

            if i % save_interval == 0 or i == end_page:
                save_to_csv("output/careers360_colleges_partial.csv")
                logging.warning(f"Partial data saved after scraping page {i}")

def parse_college_detail_page(college):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    if college["College URL"] == "N/A":
        driver.quit()
        return college

    try:
        driver.set_page_load_timeout(30)
        driver.get(college["College URL"])
        sleep(random.uniform(3, 5))

        detail_soup = BeautifulSoup(driver.page_source, 'html.parser')

        college["Course Title"] = detail_soup.find('h1').text.strip() if detail_soup.find('h1') else "N/A"
        college["Total Fees"] = detail_soup.find('div', class_='fee').text.strip() if detail_soup.find('div', class_='fee') else "N/A"
        college["Course Duration"] = detail_soup.find('div', class_='course_detail_para').find_all('div')[1].text.strip() if detail_soup.find('div', class_='course_detail_para') else "N/A"
        college["Eligibility Criteria"] = detail_soup.find('div', id='eligiblity').find('div', class_='data_html_blk').text.strip() if detail_soup.find('div', id='eligiblity') else "N/A"

    except Exception as e:
        logging.error(f"Error fetching details for {college['College Name']}: {e}")

    driver.quit()
    return college

def scrape_college_details(save_interval=10):
    global college_list
    total_colleges = len(college_list)

    with ThreadPoolExecutor(max_workers=6) as executor:
        for i, result in enumerate(executor.map(parse_college_detail_page, college_list)):
            college_list[i] = result

            if (i + 1) % save_interval == 0 or i + 1 == total_colleges:
                save_to_csv("output/careers360_colleges_partial.csv")
                logging.warning(f"Partial data saved after scraping {i+1} college details")

def save_to_csv(filename="output/careers360_colleges.csv"):
    df = pd.DataFrame(college_list)
    df.to_csv(filename, index=False)

async def main(start_page=1, end_page=5):
    start_time = time()

    await scrape_main_pages(start_page, end_page)
    scrape_college_details()

    save_to_csv("output/careers360_colleges.csv")
    logging.warning("Final data saved to output/careers360_colleges.csv")
    logging.warning(f"Total execution time: {time() - start_time:.2f} seconds")
