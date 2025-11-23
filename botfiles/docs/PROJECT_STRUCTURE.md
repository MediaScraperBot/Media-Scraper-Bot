# Project Structure

## Root Directory (`Downloading Software\Scraper\`)

### Launch Files
- **`main.py`** - Main entry point (run this to start the scraper)
- **`run_scraper.bat`** - Windows batch file for easy launching

### Documentation
- **`README.md`** - Complete documentation
- **`INSTRUCTIONS.md`** - Quick start guide
- **`HISTORY_FEATURE.md`** - Download history tracking guide
- **`SCANNING_GUIDE.md`** - Sitemap scanning and gallery-dl guide

### Data Directory
- **`Downloads/`** - Downloaded media files (auto-created)

## Bot Files Directory (`botfiles\`)

### Core Application Files
- **`__init__.py`** - Package initialization
- **`gui.py`** - Main GUI application
- **`reddit_scraper.py`** - Reddit scraping module
- **`twitter_scraper.py`** - Twitter scraping module
- **`website_scraper.py`** - Website scraping module
- **`sitemap_scanner.py`** - Sitemap scanner and gallery-dl integration
- **`history.py`** - Download history tracker
- **`utils.py`** - Utility functions

### Configuration Files
- **`config.json`** - API credentials (Reddit, Twitter)
- **`usernames.txt`** - List of usernames to scrape
- **`subreddit.txt`** - List of subreddits to scrape
- **`websites.txt`** - List of websites to scrape
- **`requirements.txt`** - Python package dependencies

### Data Files (auto-created)
- **`download_history.json`** - Download tracking history

## How to Use

### To Launch the App:
1. **Double-click:** `run_scraper.bat`
2. **Or run:** `python main.py`
3. **Or run:** `python -m botfiles.gui`

### To Configure:
1. Edit files in `botfiles/` directory:
   - `config.json` - API settings
   - `usernames.txt` - Add usernames
   - `subreddit.txt` - Add subreddits
   - `websites.txt` - Add websites

### To Install Dependencies:
```powershell
pip install -r botfiles/requirements.txt
```

## Benefits of This Structure

✅ **Clean root directory** - Only launcher and documentation visible  
✅ **Organized code** - All bot code contained in `botfiles/`  
✅ **Easy access** - Config files grouped together  
✅ **Portable** - Everything self-contained  
✅ **Clear separation** - User files vs. bot files  

## File Locations Summary

| What | Where |
|------|-------|
| Launch app | `main.py` or `run_scraper.bat` |
| Bot code | `botfiles/*.py` |
| Configuration | `botfiles/*.json`, `botfiles/*.txt` |
| Documentation | `*.md` in root |
| Downloads | `Downloads/` (auto-created) |
| History | `botfiles/download_history.json` |

## Notes

- All configuration files are automatically accessed from `botfiles/`
- No need to manually edit paths
- The app handles everything automatically
- History and config stay with the bot files
