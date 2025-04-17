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
# Extract Admission Process
# ----------------------------
def extract_admission_process(driver, base_url):
    admission_url = base_url.rstrip('/') + "/admission"
    driver.get(admission_url)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    admission_section = soup.find("section", id="admission_section_admission_process")
    if not admission_section:
        admission_section = soup.find("div", class_="wikiContents")

    if admission_section:
        paragraphs = admission_section.find_all("p")
        para_text = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        table = admission_section.find("table")
        table_text = ""
        if table:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                row_text = " | ".join(cell.get_text(strip=True) for cell in cells)
                table_text += row_text + "\n"

        combined = para_text.strip()
        if table_text:
            combined += "\n\nADMISSION HIGHLIGHTS:\n" + table_text.strip()

        return combined if combined else "N/A"

    return "N/A"

# ----------------------------
# Extract Course Details Function
# ----------------------------
def extract_course_details(driver, course_url):
    driver.get(course_url)
    time.sleep(4)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    eligibility = ""
    eligibility_block = soup.find("div", class_="ba258d")
    if eligibility_block:
        eligibility = eligibility_block.get_text(separator=" ", strip=True)

    highlights = ""
    highlight_section = soup.find("div", id=lambda x: x and x.startswith("EdContent_undefined_bip_section_highlights"))
    if highlight_section:
        highlights = highlight_section.get_text(separator=" ", strip=True)

    whats_new = ""
    whats_new_section = soup.find("div", class_="paper-card boxShadow baac")
    if whats_new_section:
        whats_new = whats_new_section.get_text(separator=" ", strip=True)

    admission_process = extract_admission_process(driver, course_url)

    return eligibility, highlights, whats_new, admission_process

# ----------------------------
# Main Script with Pagination
# ----------------------------
driver = setup_driver()

try:
    page_no = 1
    college_index = 1

    with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "College Name", "Base Fees", "Avg Salary", "College Page URL",
            "Course Name", "Course URL", "Eligibility Criteria", "Course Highlights", "What's New", "Admission Process"
        ])

    with open(OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        while True:
            page_url = f"{MAIN_URL}?pageNo={page_no}"
            logging.info(f"Loading Page {page_no}: {page_url}")
            driver.get(page_url)

            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "section[id^='tupleInstId_']"))
                )
            except:
                logging.warning("No content found or page load timeout.")
                break

            soup = BeautifulSoup(driver.page_source, "html.parser")
            ranking_items = soup.find_all("section", id=lambda x: x and x.startswith("tupleInstId_"))

            if not ranking_items:
                logging.info("No more ranking items found. Pagination complete.")
                break

            logging.info(f"Found {len(ranking_items)} colleges on page {page_no}")

            for item in ranking_items:
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

                logging.info(f"[{college_index}] {college_name} (Rank {rank}) → {course_url or 'no course page'}")

                if course_url:
                    try:
                        driver.get(course_url)
                        time.sleep(6)
                        course_page_html = driver.page_source
                        courses = extract_course_links(course_page_html)

                        for course_name, course_href in courses:
                            try:
                                eligibility, highlights, whats_new, admission_process = extract_course_details(driver, course_href)
                                writer.writerow([
                                    rank, college_name, base_fees, avg_salary, course_url,
                                    course_name, course_href, eligibility, highlights, whats_new, admission_process
                                ])
                            except Exception as e:
                                logging.warning(f"Failed course detail extraction for {course_href}: {e}")

                    except Exception as e:
                        logging.warning(f"Error scraping course links: {e}")

                csvfile.flush()
                os.fsync(csvfile.fileno())

                if college_index % BACKUP_EVERY == 0:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_name = f"backup_{college_index}_{ts}.csv"
                    shutil.copy(OUTPUT_FILE, backup_name)
                    logging.info(f"  → backup saved: {backup_name}")

                college_index += 1

            page_no += 1

    logging.info("Finished! Full data saved to " + OUTPUT_FILE)

finally:
    driver.quit()
