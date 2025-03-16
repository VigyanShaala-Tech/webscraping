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

## Benchmarks

|Device                       |CPU (model, cores+threads, clock)|RAM (size, speed)                                   |GPU (model, vram, clock)|
|-----------------------------|---------------------------------|----------------------------------------------------|------------------------|
|PC                           |Ryzen 7 3700x, 8+16, 4.2GHz      |32GB DDR4 @ 3000MHz                                 |RX 5700 XT, 8GB, 1750MHz|
|Laptop                       |Ryzen 3 3250U, 2+4, 2.6GHz       |6GB DDR4 @ 2400 MHz                                 |none (integrated Vega 3)|
|Raspi 5                      |ARM Cortex A-76, 4+0, 2.4GHz     |8GB DDR4 @ 4267 MHz                                 |VideoCore VII, -, 800MHz|
|Github Actions*              |AMD EPYC 7763, 4, 2.2GHz         |16GB DDR4 @ unknown                                 |none                    |


|Device                       |Pytesseract (Single-threaded)|EasyOCR (Single-threaded)                           |Pytesseract (Multithreaded)|EasyOCR (Multithreaded)|
|-----------------------------|-----------------------------|----------------------------------------------------|---------------------------|-----------------------|
|PC                           |143.14                       |804.62                                              |41                         |564.27                 |
|Laptop                       |933.23                       |1749.2                                              |788.3                      |1592.45                |
|Raspi 5                      |619.41                       |1508.53                                             |461.13                     |1228                   |
|Github Actions               |300                          |1486.82                                             |Process Timeout            |1180.09                |
