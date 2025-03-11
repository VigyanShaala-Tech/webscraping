import asyncio
from src.scrapers.colleges import careers360

if __name__ == "__main__":
    start_page = int(input("Enter start page: ").strip())
    end_page = int(input("Enter end page: ").strip())
    asyncio.run(careers360.main(start_page=start_page, end_page=end_page))
