"""Crawl a set of seed URLs listed in crawl_urls.txt and download media."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterable, List

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from ..history import DownloadHistory
from ..website_scraper import WebsiteScraper

BASE_DIR = Path(__file__).resolve().parent.parent
URLS_FILE = BASE_DIR / "crawl_urls.txt"
DOWNLOADS_DIR = BASE_DIR / "Downloads"
CRAWL_DELAY = 1  # seconds between requests
MAX_PAGES = 1000  # safety limit per root URL


def _load_seeds() -> List[str]:
    if not URLS_FILE.exists():
        print(f"Please create {URLS_FILE} with one URL per line.")
        sys.exit(1)

    with URLS_FILE.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def main() -> None:
    start_urls = _load_seeds()
    history = DownloadHistory(str(BASE_DIR / "download_history.json"))
    scraper = WebsiteScraper(history=history)

    for root_url in start_urls:
        print(f"\nStarting crawl from: {root_url}")
        visited = set()
        pages_to_visit = [root_url]
        pages_crawled = 0
        domain = urlparse(root_url).netloc
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
                        if urlparse(full_url).netloc == domain and full_url not in visited:
                            pages_to_visit.append(full_url)
                pages_crawled += 1
                time.sleep(CRAWL_DELAY)
            except Exception as exc:
                print(f"Error crawling {url}: {exc}")
        print(f"Crawl complete for {root_url}. {pages_crawled} pages visited.")

    print("\nAll URLs processed.")


if __name__ == "__main__":
    main()
