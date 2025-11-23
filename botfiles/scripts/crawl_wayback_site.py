"""Crawl an archived Stickaps site starting from a seed URL."""

from __future__ import annotations

import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..history import DownloadHistory
from ..website_scraper import WebsiteScraper

BASE_DIR = Path(__file__).resolve().parent.parent
START_URL = "https://web.archive.org/web/20220101000000im_/http://stickaps.com/"
DOWNLOADS_DIR = BASE_DIR / "Downloads"
CRAWL_DELAY = 1  # seconds between requests
MAX_PAGES = 1000  # safety limit


def main() -> None:
    visited = set()
    pages_to_visit = [START_URL]

    history = DownloadHistory(str(BASE_DIR / "download_history.json"))
    scraper = WebsiteScraper(history=history)

    print(f"Starting crawl from: {START_URL}")

    pages_crawled = 0
    while pages_to_visit and pages_crawled < MAX_PAGES:
        url = pages_to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        print(f"\nCrawling page: {url}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            downloaded = scraper.scrape_url(
                url,
                str(DOWNLOADS_DIR),
                progress_callback=print,
                max_pages=1,
                scroll_count=1,
            )
            if downloaded:
                print(f"✓ Downloaded: {downloaded}")
            for anchor in soup.find_all("a", href=True):
                link = str(anchor["href"])
                if link.startswith(("/", "http")):
                    full_url = urljoin(url, link)
                    if "web.archive.org" in full_url and "stickaps.com" in full_url and full_url not in visited:
                        pages_to_visit.append(full_url)
            pages_crawled += 1
            time.sleep(CRAWL_DELAY)
        except Exception as exc:
            print(f"Error crawling {url}: {exc}")

    print(f"\nCrawl complete. {pages_crawled} pages visited.")


if __name__ == "__main__":
    main()
