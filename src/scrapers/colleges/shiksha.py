import csv
import os
import shutil
import logging
import time
from time import sleep
from datetime import datetime
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ----------------------------
# CONFIG
# ----------------------------
MAIN_URL = "https://www.shiksha.com/engineering/ranking/top-engineering-colleges-in-india/44-2-0-0-0"
OUTPUT_FILE = "engineering_colleges_and_courses.csv"
BACKUP_EVERY = 5

# ----------------------------
# Logging Setup
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ----------------------------
# Setup Driver Function
# ----------------------------
def setup_driver():
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")
    options.add_argument("window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # Hide webdriver
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            """
        },
    )
    return driver

# ----------------------------
# Extract Course Links Function
# ----------------------------
def extract_course_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    base_url = "https://www.shiksha.com"
    links = soup.find_all("a", class_="_69c7 ripple dark")

    course_info = []
    for link in links:
        course_name = link.get_text(strip=True)
        href = link.get("href", "")
        full_url = base_url + href if href.startswith("/") else href
        course_info.append((course_name, full_url))
    return course_info

# ----------------------------
# Main Script
# ----------------------------
driver = setup_driver()

try:
    logging.info(f"Loading main page: {MAIN_URL}")
    driver.get(MAIN_URL)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "section[id^='tupleInstId_']"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")
    ranking_items = soup.find_all("section", id=lambda x: x and x.startswith("tupleInstId_"))
    total = len(ranking_items)
    logging.info(f"Found {total} colleges")

    # Write CSV header
    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Rank", "College Name", "Base Fees", "Avg Salary", "College Page URL", "Course Name", "Course URL"])

    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        for idx, item in enumerate(ranking_items, start=1):
            name_tag = item.select_one("a.rank_clg h4")
            college_name = name_tag.text.strip() if name_tag else "N/A"

            rank_tag = item.select_one(".rank_section span.circleText")
            rank = rank_tag.text.strip() if rank_tag else "N/A"

            fee_label = item.find(lambda tag: tag.name == "div" and tag.get_text(strip=True).startswith("Fees:"))
            base_fees = fee_label.find_next("div").text.strip() if fee_label else "N/A"

            salary_label = item.find(lambda tag: tag.name == "div" and tag.get_text(strip=True).startswith("Salary :"))
            avg_salary = salary_label.find_next("div").text.strip() if salary_label else "N/A"

            course_link = item.find("a", href=True, string="Courses")
            course_url = urljoin("https://www.shiksha.com", course_link["href"]) if course_link else None

            logging.info(f"[{idx}/{total}] {college_name} (Rank {rank}) → {course_url or 'no course page'}")

            if course_url:
                try:
                    driver.get(course_url)
                    time.sleep(6)
                    course_page_html = driver.page_source
                    courses = extract_course_links(course_page_html)

                    for course_name, course_href in courses:
                        writer.writerow([rank, college_name, base_fees, avg_salary, course_url, course_name, course_href])
                except Exception as e:
                    logging.warning(f"Error scraping course links: {e}")

            csvfile.flush()
            os.fsync(csvfile.fileno())

            if idx % BACKUP_EVERY == 0:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{idx}_{ts}.csv"
                shutil.copy(OUTPUT_FILE, backup_name)
                logging.info(f"  → backup saved: {backup_name}")

    logging.info("Finished! Full data saved to " + OUTPUT_FILE)

finally:
    driver.quit()
