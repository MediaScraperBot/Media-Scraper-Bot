# Instructions for using your Media Scraper Bot

## Quick Start Guide

### Step 1: Install Required Packages
Open PowerShell in the Scraper folder and run:
```powershell
pip install -r botfiles/requirements.txt
```

### Step 2: Get Reddit API Credentials
1. Go to https://www.reddit.com/prefs/apps
2. Scroll down and click "create another app..."
3. Fill in:
   - Name: "My Media Scraper" (or any name)
   - App type: Select "script"
   - Description: (optional)
   - Redirect URI: http://localhost:8080
4. Click "create app"
5. Copy these values:
   - **Client ID**: The string under "personal use script"
   - **Client Secret**: The "secret" field

### Step 3: Configure the Application
1. Run the application:
   ```powershell
   python main.py
   ```

2. Go to the "Settings" tab

3. Enter your Reddit credentials:
   - Paste Client ID
   - Paste Client Secret
   - User Agent: Keep as "MediaScraper/1.0" or change to "MyBot/1.0"

4. Click "Save Settings"

### Step 4: Start Scraping!

**To scrape subreddits:**
1. Go to "Reddit" tab
2. In the "Subreddits" section, type a subreddit name (e.g., "pics", "gifs", "videos")
3. Click "Add"
4. Repeat for more subreddits
5. Click "Scrape All" to download media

**To scrape Reddit users:**
1. In the "Reddit Users" section, type a username (without u/)
2. Click "Add"
3. Click "Scrape All"

**To scrape websites:**
1. Go to "Websites" tab
2. Enter a URL (e.g., "https://example.com/gallery")
3. Or enter a sitemap URL (e.g., "https://example.com/sitemap.xml")
4. Click "Add"
5. Click "Scrape All"

### Where are my downloads?
By default, media is saved to:
- `Downloads/subreddit_name/` for subreddit content
- `Downloads/username/` for user content
- `Downloads/website_domain/` for website content

You can change the download location in the Settings tab.

### Where are the configuration files?
All configuration and data files are in the `botfiles/` directory:
- `botfiles/config.json` - API credentials
- `botfiles/usernames.txt` - User list
- `botfiles/subreddit.txt` - Subreddit list
- `botfiles/websites.txt` - Website list
- `botfiles/download_history.json` - Download tracking

### Tips:
- The activity log in the Settings tab shows what's being downloaded
- You can add/remove sources anytime
- The app automatically skips files that already exist
- Scraping runs in the background so the app stays responsive

### Note about Twitter:
Twitter scraping requires API credentials which are harder to get. Focus on Reddit and websites first, or apply for Twitter Developer access if needed.
