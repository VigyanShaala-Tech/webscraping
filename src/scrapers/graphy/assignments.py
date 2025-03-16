import os
import csv
import requests
import logging
from datetime import datetime

# ========== Setup ==========

# Create folders for output and logs
os.makedirs("logs", exist_ok=True)
os.makedirs("output", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/vigyanshaala_scraper.log"),
        logging.StreamHandler()
    ]
)

# Constants
LOGIN_URL = "https://mytribe.vigyanshaala.com/s/authenticate"
ASSIGNMENT_ID = "65c5f301e4b051b50cfd6121"
BASE_URL = f"https://mytribe.vigyanshaala.com/s/assignments/{ASSIGNMENT_ID}/submissions"
OUTPUT_FILE = f"output/assignment_submissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ========== Functions ==========

def login_to_portal(session, email, password):
    payload = {
        "email": email,
        "password": password,
        "age": "",
        "url": "/t/public/login"
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://mytribe.vigyanshaala.com",
        "Referer": "https://mytribe.vigyanshaala.com/t/public/login"
    }

    response = session.post(LOGIN_URL, headers=headers, data=payload)
    if response.status_code == 200:
        logging.info("Login successful.")
    else:
        logging.error(f"Login failed with status code {response.status_code}")
        raise Exception("Login failed")

def fetch_submissions(session, start, length=50):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://mytribe.vigyanshaala.com/s/assignments",
        "X-Requested-With": "XMLHttpRequest"
    }
    params = {
        "draw": 1,
        "start": start,
        "length": length,
        "search[value]": "",
        "search[regex]": "false",
        "queries": "{}"
    }

    try:
        response = session.get(BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        logging.error(f"Error fetching data for start={start}: {e}")
        return None

def write_to_csv(writer, data):
    for item in data:
        name = f"{item.get('user', {}).get('fname', '')} {item.get('user', {}).get('lname', '')}".strip()
        email = item.get('user', {}).get('email', '')
        status = item.get('status', '')
        submitted_on = item.get('createdDate', '')
        answer_preview = str(item.get('data', ''))[:100]
        writer.writerow([name, email, status, submitted_on, answer_preview])

def scrape_assignment_submissions(email, password):
    session = requests.Session()
    login_to_portal(session, email, password)

    start = 0
    length = 50

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Learner Name", "Email", "Status", "Submission Date", "Answer Preview"])

        while True:
            data = fetch_submissions(session, start, length)
            if data is None:
                logging.error("Stopping due to fetch error.")
                break
            if not data:
                logging.info("No more data found. Scraping complete.")
                break

            write_to_csv(writer, data)
            logging.info(f"Fetched and saved {len(data)} records from start={start}")
            start += length

    logging.info(f"All data saved to {OUTPUT_FILE}")

# ========== Entry Point ==========

if __name__ == "__main__":
    USER_EMAIL = "username@vigyanshaala.com"
    USER_PASSWORD = "user'spassword"  # Consider reading this securely from env or a secrets file

    try:
        scrape_assignment_submissions(USER_EMAIL, USER_PASSWORD)
    except Exception as e:
        logging.error(f"Scraper terminated with error: {e}")
