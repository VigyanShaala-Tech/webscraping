import csv
import os
import shutil
import logging
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
BACKUP_EVERY = 5   # make a timestamped backup after every 5 colleges

# ----------------------------
# Setup logging
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ----------------------------
# Chrome headless options
# ----------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument("--log-level=3")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
)

# ----------------------------
# Initialize WebDriver
# ----------------------------
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

try:
    logging.info(f"Loading main page: {MAIN_URL}")
    driver.get(MAIN_URL)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "section[id^='tupleInstId_']"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")
    ranking_items = soup.find_all("section", id=lambda x: x and x.startswith("tupleInstId_"))
    total = len(ranking_items)
    logging.info(f"Found {total} colleges")

    # Create the output CSV with header
    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "College Name", "Base Fees", "Avg Salary", "College Page URL",
            "Course Type", "Tuition Fees", "Eligibility"
        ])

    # Open in append mode for incremental writes
    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        for idx, item in enumerate(ranking_items, start=1):
            # --- extract main info ---
            name_tag = item.select_one("a.rank_clg h4")
            college_name = name_tag.text.strip() if name_tag else "N/A"

            rank_tag = item.select_one(".rank_section span.circleText")
            rank = rank_tag.text.strip() if rank_tag else "N/A"

            fee_label = item.find(lambda tag: tag.name == "div" and tag.get_text(strip=True).startswith("Fees:"))
            base_fees = fee_label.find_next("div").text.strip() if fee_label else "N/A"

            salary_label = item.find(lambda tag: tag.name == "div" and tag.get_text(strip=True).startswith("Salary :"))
            avg_salary = salary_label.find_next("div").text.strip() if salary_label else "N/A"

            course_link = item.find("a", href=True, text="Courses")
            course_url = urljoin("https://www.shiksha.com", course_link["href"]) if course_link else None

            logging.info(f"[{idx}/{total}] {college_name} (Rank {rank}) → {course_url or 'no courses'}")

            # --- scrape course table if available ---
            if course_url:
                try:
                    driver.get(course_url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table._1708"))
                    )
                    sleep(1)  # allow JS to render
                    csoup = BeautifulSoup(driver.page_source, "html.parser")
                    tbody = csoup.find("table", class_="_1708").find("tbody")

                    for row in tbody.find_all("tr"):
                        cols = row.find_all("td")
                        course_type = cols[0].get_text(strip=True)
                        tuition     = cols[1].get_text(strAip=True)
                        elig        = cols[2].get_text(strip=True)

                        writer.writerow([
                            rank, college_name, base_fees, avg_salary, course_url,
                            course_type, tuition, elig
                        ])

                except Exception as e:
                    logging.error(f"  ✗ failed to scrape courses for {college_name}: {e}")
                    writer.writerow([
                        rank, college_name, base_fees, avg_salary,
                        course_url, "N/A", "N/A", "N/A"
                    ])
            else:
                # No course URL found
                writer.writerow([
                    rank, college_name, base_fees, avg_salary,
                    "N/A", "N/A", "N/A", "N/A"
                ])

            # --- PARTIAL SAVE: flush & optional backup ---
            csvfile.flush()
            os.fsync(csvfile.fileno())

            if idx % BACKUP_EVERY == 0:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{idx}_{ts}.csv"
                shutil.copy(OUTPUT_FILE, backup_name)
                logging.info(f"  → backup saved: {backup_name}")

    logging.info("✅ Finished! Full data in " + OUTPUT_FILE)

finally:
    driver.quit()
