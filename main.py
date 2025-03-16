import asyncio
from src.scrapers.colleges import careers360
from src.scrapers.graphy.assignments import GraphyAssignmentScraper
import logging

scraper = 1 

if __name__ == "__main__":
    if scraper == 1 :
        start_page = int(input("Enter start page: ").strip())
        end_page = int(input("Enter end page: ").strip())
        asyncio.run(careers360.main(start_page=start_page, end_page=end_page))
    else:
        email = "muskan.gupta@vigyanshaala.com"
        password = "VS@123"
        assignment_id = "65c5f301e4b051b50cfd6121"

        try:
            scraper = GraphyAssignmentScraper(email, password, assignment_id)
            scraper.run()
        except Exception as e:
            logging.error(f"Scraper terminated with error: {e}")
