import asyncio
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd
import os
import random
from time import time, sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor
import logging

from src.core.http import HTTP

# Create folders for logs and output files
os.makedirs("logs", exist_ok=True)
os.makedirs("output", exist_ok=True)

# Configure logging to output info-level messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/scraper.log"),
        logging.StreamHandler()
    ]
)

# Adjust external libraries' log levels to reduce verbosity
logging.getLogger("WDM").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

college_list = []
# Global partial filename (will be set at start time in main)
PARTIAL_FILENAME = "output/careers360_colleges_partial.csv"

def generate_careers360_url(page):
    base_url = "https://www.careers360.com/colleges/india-colleges-fctp"
    query_params = {
        "page": page,
        "degree": "64,2,72,14,6,65,100,101,150,75,168,9,211",
        "sort_by": "3"
    }
    encoded_params = urllib.parse.urlencode(query_params, safe=",")
    return f"{base_url}?{encoded_params}"

def generate_timestamped_filename(prefix="careers360_colleges"):
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"output/{prefix}_{now}.csv"

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
                save_to_csv(PARTIAL_FILENAME)
                logging.info(f"Partial data saved after scraping page {i}")

def parse_college_detail_page(college):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    if college.get("College URL") == "N/A":
        driver.quit()
        return college

    try:
        driver.set_page_load_timeout(30)
        driver.get(college["College URL"])
        sleep(random.uniform(3, 5))

        detail_soup = BeautifulSoup(driver.page_source, "html.parser")

        # Course Title
        title_tag = detail_soup.find("h1")
        college["Course Title"] = title_tag.text.strip() if title_tag else "N/A"

        # Total Fees (main section)
        fee_tag = detail_soup.find("div", class_="fee")
        college["Total Fees"] = fee_tag.text.strip() if fee_tag else "N/A"

        # Course Duration and Mode
        course_detail_divs = detail_soup.select(".course_detail_para div")
        for div in course_detail_divs:
            label = div.find("p")
            value = div.find("span")
            if label and value:
                label_text = label.text.strip().lower()
                if label_text == "duration":
                    college["Course Duration"] = value.text.strip()
                elif label_text == "mode":
                    college["Course Mode"] = value.text.strip()

        college.setdefault("Course Duration", "N/A")
        college.setdefault("Course Mode", "N/A")

        # Course Description
        desc_tag = detail_soup.select_one(".list_tick_style p")
        college["Course Description"] = desc_tag.text.strip() if desc_tag else "N/A"

        # Eligibility Criteria
        eligibility_tag = detail_soup.find("div", id="eligiblity")
        if eligibility_tag:
            criteria_tag = eligibility_tag.find("div", class_="data_html_blk")
            college["Eligibility Criteria"] = criteria_tag.text.strip() if criteria_tag else "N/A"
        else:
            college["Eligibility Criteria"] = "N/A"

        # Selection Process (Admission Details)
        admission_tag = detail_soup.find("div", id="admission_detail")
        if admission_tag:
            selection_para = admission_tag.find("div", class_="data_html_blk")
            college["Selection Process"] = selection_para.text.strip() if selection_para else "N/A"
        else:
            college["Selection Process"] = "N/A"

        # Quick Facts block
        quick_facts = detail_soup.select(".quick_facts_table td")
        for td in quick_facts:
            label_tag = td.select_one(".right_upr")
            value_tag = td.select_one(".right_btm span")
            if label_tag and value_tag:
                label = label_tag.text.strip().lower()
                value = value_tag.text.strip()
                if label == "total fees" and (college.get("Total Fees", "N/A") == "N/A"):
                    college["Total Fees"] = value
                elif label == "exam":
                    college["Entrance Exam"] = value
                elif label == "seats":
                    college["Total Seats"] = value

        college.setdefault("Entrance Exam", "N/A")
        college.setdefault("Total Seats", "N/A")

    except Exception as e:
        logging.error(f"Error fetching details for {college.get('College Name', 'Unknown College')}: {e}")

    driver.quit()
    return college

def scrape_college_details(save_interval=10):
    global college_list
    total_colleges = len(college_list)

    with ThreadPoolExecutor(max_workers=6) as executor:
        for i, result in enumerate(executor.map(parse_college_detail_page, college_list)):
            college_list[i] = result

            if (i + 1) % save_interval == 0 or i + 1 == total_colleges:
                save_to_csv(PARTIAL_FILENAME)
                logging.info(f"Partial data saved after scraping {i+1} college details")

def save_to_csv(filename):
    df = pd.DataFrame(college_list)
    df.to_csv(filename, index=False)

async def main(start_page=1, end_page=5):
    global PARTIAL_FILENAME
    start_time = time()
    # Compute a start timestamp that remains fixed for all partial saves
    start_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    PARTIAL_FILENAME = f"output/careers360_colleges_partial_{start_timestamp}.csv"

    await scrape_main_pages(start_page, end_page)
    scrape_college_details()

    final_filename = generate_timestamped_filename()
    save_to_csv(final_filename)
    logging.info(f"Final data saved to {final_filename}")
    logging.info(f"Total execution time: {time() - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
