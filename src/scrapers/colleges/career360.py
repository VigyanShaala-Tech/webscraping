from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse
import pandas as pd
from time import sleep
from random import randint
import time

# List to store extracted data
college_list = []

# Function to generate Careers360 URL
def generate_careers360_url(page):
    base_url = "https://www.careers360.com/colleges/india-colleges-fctp"
    query_params = {
        "page": page,
        "degree": "64,2,72,14,6,65,100,101,150,75,168,9,211",
        "sort_by": "3"
    }
    encoded_params = urllib.parse.urlencode(query_params, safe=",")
    return f"{base_url}?{encoded_params}"

# Function to parse data from the main page
def parse_main_page(soup):
    colleges = soup.find_all("div", class_="card_block")
    for college in colleges:
        college_soup = BeautifulSoup(str(college), 'html.parser')

        try:
            college_name = college_soup.find("h3", class_="college_name").text.strip()
        except AttributeError:
            college_name = "N/A"

        try:
            location = college_soup.find("span", class_="location").text.strip()
        except AttributeError:
            location = "N/A"

        try:
            fees = college_soup.find("li", string=lambda s: "Fees :" in s if s else False).text.replace("Fees :", "").strip()
        except AttributeError:
            fees = "N/A"

        try:
            rating = college_soup.find("span", class_="star_text").text.strip()
        except AttributeError:
            rating = "N/A"

        try:
            reviews = college_soup.find("span", class_="review_text").text.strip()
        except AttributeError:
            reviews = "N/A"

        try:
            nirf_ranking = college_soup.find("div", class_="ranking_strip").text.strip()
        except AttributeError:
            nirf_ranking = "N/A"

        # Extract the link to the college's detail page
        try:
            link = college_soup.find('a', class_='general_text')['href']
            college_url = link
        except (AttributeError, TypeError):
            college_url = "N/A"

        # Store the extracted data
        college_list.append({
            "College Name": college_name,
            "Location": location,
            "Fees": fees,
            "Rating": rating,
            "Reviews": reviews,
            "NIRF Ranking": nirf_ranking,
            "College URL": college_url
        })

# Function to parse additional data from the college's detail page
def parse_college_detail_page(driver, college):
    print("Working.......................................")
    if college["College URL"] == "N/A":
        return

    driver.get(college["College URL"])
    sleep(randint(5, 10))  # Allow page to load

    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract the course title
    try:
        course_title = detail_soup.find('h1').text.strip()
        college["Course Title"] = course_title
    except AttributeError:
        college["Course Title"] = "N/A"

    # Extract the total fees
    try:
        total_fees = detail_soup.find('div', class_='fee').text.strip()
        college["Total Fees"] = total_fees
    except AttributeError:
        college["Total Fees"] = "N/A"

    # Extract the course duration
    try:
        course_duration = detail_soup.find('div', class_='course_detail_para').find_all('div')[1].text.strip()
        college["Course Duration"] = course_duration
    except (AttributeError, IndexError):
        college["Course Duration"] = "N/A"

    # Extract the eligibility criteria
    try:
        eligibility_criteria = detail_soup.find('div', id='eligiblity').find('div', class_='data_html_blk').text.strip()
        college["Eligibility Criteria"] = eligibility_criteria
    except AttributeError:
        college["Eligibility Criteria"] = "N/A"

    # Extract the important dates
    important_dates = []
    try:
        dates_table = detail_soup.find('div', id='important_date').find('table', class_='table_blk')
        for row in dates_table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) == 2:
                exam_event = cols[0].text.strip()
                date = cols[1].text.strip()
                important_dates.append(f"{exam_event}: {date}")
        college["Important Dates"] = "; ".join(important_dates)
    except AttributeError:
        college["Important Dates"] = "N/A"

    # Extract the top exams accepted
    top_exams = []
    try:
        exams_block = detail_soup.find('div', id='exams')
        for exam in exams_block.find_all('h3'):
            top_exams.append(exam.text.strip())
        college["Top Exams Accepted"] = ", ".join(top_exams)
    except AttributeError:
        college["Top Exams Accepted"] = "N/A"

    # Extract other popular courses in the college
    other_courses = []
    try:
        courses_block = detail_soup.find('div', class_='know_more_about_college')
        for course in courses_block.find_all('a'):
            other_courses.append(course.text.strip())
        college["Other Popular Courses"] = ", ".join(other_courses)
    except AttributeError:
        college["Other Popular Courses"] = "N/A"

# Set up Selenium
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode for efficiency
options.add_experimental_option("excludeSwitches", ["enable-automation"])
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Define start and end pages
start_page = 1
end_page = 50  

start_time = time.time()
print("start_time",start_time)
# Scraping loop for main pages
pageNum = 1
for page in range(start_page, end_page + 1):
    url = generate_careers360_url(page)
    driver.get(url)
    sleep(randint(3, 5))  # Allow page to load

    main_soup = BeautifulSoup(driver.page_source, 'html.parser')
    parse_main_page(main_soup)
    print(f"Scrapped Main Page {pageNum} Data.............")
    pageNum+=1

# Scraping loop for college detail pages
pageNum = 1
for college in college_list:
    parse_college_detail_page(driver, college)
    print(f"Scrapped Colleges Data Inside the link {pageNum} Data.............")
    pageNum+=1


driver.quit()

# Convert to DataFrame and save
df = pd.DataFrame(college_list)
df.to_csv("careers360_colleges.csv", index=False)
print("Data saved to careers360_colleges.csv")

end_time = time.time()

execution_time = end_time - start_time
print(f"Execution time: {execution_time} seconds")