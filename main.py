from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse
import pandas as pd
from time import sleep
from random import randint

# List to store extracted data
job_list = []

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

print(generate_careers360_url(1))

# Function to parse data from page soup
def parse_college_data(page_soup):
    for college in page_soup:
        soup = BeautifulSoup(str(college), 'html.parser')

        try:
            college_name = soup.find("h3", class_="college_name").text.strip()
        except AttributeError:
            college_name = "N/A"

        try:
            location = soup.find("span", class_="location").text.strip()
        except AttributeError:
            location = "N/A"
            
        try:
            # Try to find the fees element and extract the text after "Fees :"
            fees = soup.find("li", text=lambda t: "Fees :" in t if t else False).text.replace("Fees :", "").strip()
        except AttributeError:
            fees = "N/A"
            
        try:
            rating = soup.find("span", class_="star_text").text.strip()
        except AttributeError:
            rating = "N/A"

        try:
            reviews = soup.find("span", class_="review_text").text.strip()
        except AttributeError:
            reviews = "N/A"

        try:
            nirf_ranking = soup.find("div", class_="ranking_strip").text.strip()
        except AttributeError:
            nirf_ranking = "N/A"
            
        link = soup.find('a', class_='general_text')
        if link:
            link_text = link.get_text(strip=True)
            link_url = link.get('href')
            print(f'Text: {link_text}')
            print(f'URL: {link_url}')
        else:
            print("No link found with class 'general_text'")
        
        courses = [a.text.strip() for a in soup.select("div.snippet_block ul.snippet_list li a")]

        important_links = {a.text.strip(): a["href"] for a in soup.select("div.important_links ul.links_list li a")}

        # Store data in list
        job_list.append({
            "College Name": college_name,
            "Location": location,
            "Rating": rating,
            "Reviews": reviews,
            "NIRF Ranking": nirf_ranking,
            "Courses Offered": ", ".join(courses),
            link_text: link_url
        })


# Set up Selenium
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode for efficiency
options.add_experimental_option("excludeSwitches", ["enable-automation"])
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Define start and end pages
start_page = 1
page_end = 4  # Adjust as needed

# Scraping loop
for i in range(start_page, page_end):
    url = generate_careers360_url(i)
    driver.get(url)
    sleep(randint(5, 10))  # Allow page to load

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    page_soup = soup.find_all("div", class_="card_block")  # Adjust class to match actual structure
    parse_college_data(page_soup)

driver.quit()

# Convert to DataFrame and save
df = pd.DataFrame(job_list)
df.to_csv("careers360_colleges.csv", index=False)
print("Data saved to careers360_colleges.csv")
