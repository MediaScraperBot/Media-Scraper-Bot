"""Batch scrape archived Stickaps URLs using WebsiteScraper."""

from __future__ import annotations

from pathlib import Path

from ..history import DownloadHistory
from ..website_scraper import WebsiteScraper

# List of Wayback Stickaps URLs to crawl
URLS = [
    # Add your URLs here
    "https://web.archive.org/web/20220101000000im_/http://stickaps.com/wp-content/uploads/2012/01/sample_video.avi",
    # "https://web.archive.org/web/20220101000000im_/http://stickaps.com/wp-content/uploads/2012/01/another_video.avi",
]

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "Downloads"
HISTORY_FILE = BASE_DIR / "download_history.json"


def main() -> None:
    history = DownloadHistory(str(HISTORY_FILE))
    scraper = WebsiteScraper(history=history)

    for url in URLS:
        print(f"\nCrawling: {url}")
        downloaded = scraper.scrape_url(
            url,
            str(DOWNLOADS_DIR),
            progress_callback=print,
            max_pages=1,
            scroll_count=1,
        )
        if downloaded:
            print(f"✓ Downloaded: {downloaded}")
        else:
            print("No videos found or downloaded.")

    print("\nAll URLs processed.")


if __name__ == "__main__":
    main()
