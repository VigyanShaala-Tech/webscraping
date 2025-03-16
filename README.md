# Careers360 & VigyanShaala Scraper Project

This project contains Python-based web scrapers for extracting data from:
- [Careers360](https://www.careers360.com) (College listings and details)
- [VigyanShaala MyTribe](https://mytribe.vigyanshaala.com) (Assignment submissions)

## Features
- Asynchronous scraping of Careers360 main pages using `httpx`.
- Dynamic college detail extraction using `selenium`.
- Periodic partial save to avoid data loss during long scrapes.
- VigyanShaala login and assignment submission data scraping via API.
- Structured logging to file and console.
