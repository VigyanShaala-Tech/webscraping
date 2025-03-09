import asyncio
from src.scrapers.colleges import careers360


if __name__ == "__main__":
    asyncio.run(careers360.main())
