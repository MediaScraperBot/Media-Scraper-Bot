import os
from botfiles.website_scraper import WebsiteScraper
from botfiles.history import DownloadHistory

# CHANGE THIS to your target Wayback Stickaps URL
WAYBACK_URL = "https://web.archive.org/web/20220101000000im_/http://stickaps.com/wp-content/uploads/2012/01/sample_video.avi"

DOWNLOADS_DIR = "Downloads"

if __name__ == "__main__":
    history = DownloadHistory(os.path.join("botfiles", "download_history.json"))
    scraper = WebsiteScraper(history=history)
    print(f"Scraping: {WAYBACK_URL}")
    downloaded = scraper.scrape_url(WAYBACK_URL, DOWNLOADS_DIR, progress_callback=print, max_pages=1, scroll_count=1)
    print(f"Downloaded files: {downloaded}")
    if not downloaded:
        print("No videos were downloaded. Check the URL or extraction logic.")
    else:
        print("✓ Download complete!")
