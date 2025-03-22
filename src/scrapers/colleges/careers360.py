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

# Async HTTP client timeout (in seconds). Prevents long hangs.
HTTP_TIMEOUT = 30

# Maximum concurrent requests via AsyncClient
MAX_CONCURRENCY = 5 

# Save partial CSVs after every N pages / N colleges
MAIN_SAVE_INTERVAL = 5
DETAIL_SAVE_INTERVAL = 10

# Selenium WebDriver settings
HEADLESS_MODE = True  # Headless mode avoids opening Chrome GUI
PAGE_LOAD_TIMEOUT = 30  # Timeout for college detail page loading

# Sleep range between detail page fetches
DETAIL_PAGE_SLEEP_MIN = 3
DETAIL_PAGE_SLEEP_MAX = 5

# Threads for scraping college detail pages
DETAIL_SCRAPER_THREADS = 4

# Paths
PARTIAL_DIR = "output/colleges/career360"
LOG_FILE = "logs/scraper.log"
PARTIAL_FILENAME = f"{PARTIAL_DIR}/careers360_colleges_partial.csv"

os.makedirs("logs", exist_ok=True)
os.makedirs(PARTIAL_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logging.getLogger("WDM").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

college_list = []

def generate_careers360_url(page):
    base_url = "https://www.careers360.com/colleges/india-colleges-fctp"
    query_params = {
        "page": page,
        "degree": "72,14,6,101,150,168,9,184,76,154,215,191,73",
        "sort_by": "3"
    }
    encoded_params = urllib.parse.urlencode(query_params, safe=",")
    return f"{base_url}?{encoded_params}"

def generate_course_url(college_url):
    """
    Generates a filtered courses page URL for a given college.

    This function appends specific degree filters and sorting parameters
    to the base college URL to construct the full courses page URL.

    Parameters:
    - college_url (str): The base URL of the college.

    Returns:
    - str: The full URL pointing to the filtered courses page for that college.
    """
    degrees = "72,14,6,101,150,168,9,184,76,154,215,191,73"  # Degree IDs to filter specific course types
    return f"{college_url}/courses?degree={degrees}&sort_by=1"



def generate_timestamped_filename(prefix="careers360_colleges"):
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{PARTIAL_DIR}/{prefix}_{now}.csv"

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
        college_data = {
            "College Name": college.find("h3", class_="college_name").text.strip() if college.find("h3", class_="college_name") else "N/A",
            "Location": college.find("span", class_="location").text.strip() if college.find("span", class_="location") else "N/A",
            "Rating": college.find("span", class_="star_text").text.strip() if college.find("span", class_="star_text") else "N/A",
            "Reviews": college.find("span", class_="review_text").text.strip() if college.find("span", class_="review_text") else "N/A",
            "NIRF Ranking": college.find("div", class_="ranking_strip").text.strip() if college.find("div", class_="ranking_strip") else "N/A",
        }

        # Extract College URL
        url_tag = college.find("h3", class_="college_name d-md-none")
        anchor = url_tag.find("a") if url_tag else None
        college_data["College URL"] = (anchor['href'].strip()
            if anchor and anchor.has_attr('href')
            else "N/A"
        )

        local_colleges.append(college_data)

    return local_colleges

async def scrape_main_pages(start_page, end_page, save_interval=MAIN_SAVE_INTERVAL, max_concurrency=MAX_CONCURRENCY):
    global college_list
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        http = HTTP(client, max_concurrency=max_concurrency)

        tasks = [fetch_main_page(http, page) for page in range(start_page, end_page + 1)]
        results = await asyncio.gather(*tasks)

        for i, soup in enumerate(results, start=start_page):
            college_list.extend(parse_main_page(soup))
            if i % save_interval == 0 or i == end_page:
                save_to_csv(PARTIAL_FILENAME)
                logging.info(f"Partial data saved after scraping page {i}")

def parse_college_detail_page(college):
    options = Options()
    if HEADLESS_MODE:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    if college.get("College URL") == "N/A":
        driver.quit()
        return []

    course_data_list = []
    try:
        base_url = college["College URL"]
        courses_url = generate_course_url(base_url)

        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        driver.get(courses_url)
        sleep(random.uniform(DETAIL_PAGE_SLEEP_MIN, DETAIL_PAGE_SLEEP_MAX))

        course_links = set()

        # ------------------------
        # PAGINATION LOOP - COLLECT COURSE LINKS FROM EACH PAGE
        while True:
            main_soup = BeautifulSoup(driver.page_source, "html.parser")

            course_blocks = main_soup.find_all("div", class_="detail")
            for block in course_blocks:
                link_tag = block.find("h4").find("a")
                if link_tag and link_tag.get("href"):
                    course_links.add(link_tag["href"])

            # Check for NEXT button
            next_btn = main_soup.find("a", class_="pagination_list_last")
            if next_btn and next_btn.get("href"):
                next_url = next_btn["href"]
                driver.get(next_url)
                sleep(random.uniform(DETAIL_PAGE_SLEEP_MIN, DETAIL_PAGE_SLEEP_MAX))
                print("going to next page",next_url)
            else:
                break
        # ------------------------

        # Now loop through all collected course links
        for course_link in course_links:
            course = college.copy()

            full_url = course_link if course_link.startswith("http") else f"https://www.careers360.com{course_link}"
            print("Opening:", full_url)
            driver.get(full_url)
            sleep(random.uniform(DETAIL_PAGE_SLEEP_MIN, DETAIL_PAGE_SLEEP_MAX))
            detail_soup = BeautifulSoup(driver.page_source, "html.parser")

            course["Course Title"] = detail_soup.find("h1").text.strip() if detail_soup.find("h1") else "N/A"
            fee_tag = detail_soup.find("div", class_="fee")
            course["Total Fees"] = fee_tag.text.strip() if fee_tag else "N/A"

            course_detail_divs = detail_soup.select(".course_detail_para div")
            for div in course_detail_divs:
                label = div.find("p")
                value = div.find("span")
                if label and value:
                    label_text = label.text.strip().lower()
                    if label_text == "duration":
                        course["Course Duration"] = value.text.strip()
                    elif label_text == "mode":
                        course["Course Mode"] = value.text.strip()

            course.setdefault("Course Duration", "N/A")
            course.setdefault("Course Mode", "N/A")

            desc_tag = detail_soup.select_one(".list_tick_style p")
            course["Course Description"] = desc_tag.text.strip() if desc_tag else "N/A"

            eligibility_tag = detail_soup.find("div", id="eligiblity")
            if eligibility_tag:
                criteria_tag = eligibility_tag.find("div", class_="data_html_blk")
                course["Eligibility Criteria"] = criteria_tag.text.strip() if criteria_tag else "N/A"
            else:
                course["Eligibility Criteria"] = "N/A"

            admission_tag = detail_soup.find("div", id="admission_detail")
            if admission_tag:
                selection_para = admission_tag.find("div", class_="data_html_blk")
                course["Selection Process"] = selection_para.text.strip() if selection_para else "N/A"
            else:
                course["Selection Process"] = "N/A"

            quick_facts = detail_soup.select(".quick_facts_table td")
            for td in quick_facts:
                label_tag = td.select_one(".right_upr")
                value_tag = td.select_one(".right_btm span")
                if label_tag and value_tag:
                    label = label_tag.text.strip().lower()
                    value = value_tag.text.strip()
                    if label == "total fees" and (course.get("Total Fees", "N/A") == "N/A"):
                        course["Total Fees"] = value
                    elif label == "exam":
                        course["Entrance Exam"] = value
                    elif label == "seats":
                        course["Total Seats"] = value

            course.setdefault("Entrance Exam", "N/A")
            course.setdefault("Total Seats", "N/A")

            course_data_list.append(course)

    except Exception as e:
        logging.error(f"Error scraping courses for {college.get('College Name', 'Unknown College')}: {e}")

    finally:
        driver.quit()

    return course_data_list



def scrape_college_details(save_interval=DETAIL_SAVE_INTERVAL):
    global detailed_course_list
    total_colleges = len(college_list)

    with ThreadPoolExecutor(max_workers=DETAIL_SCRAPER_THREADS) as executor:
        for i, result in enumerate(executor.map(parse_college_detail_page, college_list)):
            # Handle cases where multiple courses are returned per college
            if isinstance(result, list):
                detailed_course_list.extend(result)
            elif isinstance(result, dict):
                detailed_course_list.append(result)
            else:
                logging.warning(f"Unexpected result format at index {i}: {type(result)}")

            # Save partial results after every `save_interval` colleges
            if (i + 1) % save_interval == 0 or (i + 1) == total_colleges:
                save_to_csv(PARTIAL_FILENAME)
                logging.info(f"Partial data saved after scraping {i+1} colleges")

# Global list to hold all flattened course data
detailed_course_list = []

def save_to_csv(filename):
    try:
        df = pd.DataFrame(detailed_course_list)
        df.to_csv(filename, index=False)
        logging.info(f"Data saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving CSV: {e}")


async def main(start_page=1, end_page=5, max_concurrency=MAX_CONCURRENCY):
    global PARTIAL_FILENAME
    start_time = time()
    start_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    PARTIAL_FILENAME = f"{PARTIAL_DIR}/careers360_colleges_partial_{start_timestamp}.csv"

    await scrape_main_pages(start_page, end_page, max_concurrency=max_concurrency)
    scrape_college_details()

    final_filename = generate_timestamped_filename()
    save_to_csv(final_filename)
    logging.info(f"Final data saved to {final_filename}")
    logging.info(f"Total execution time: {time() - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
