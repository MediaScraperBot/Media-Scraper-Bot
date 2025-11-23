# Media Scraper Bot

A comprehensive media scraper application with GUI for downloading media from Reddit, Twitter/X, and websites.

## Features

- **Reddit Scraper**: Download images, videos, and GIFs from:
  - Subreddits
  - User profiles
  - Support for Reddit galleries and hosted videos

- **Twitter/X Scraper**: Download media from Twitter user timelines

- **Website Scraper**: Download media from:
  - Individual web pages
  - Sitemap.xml files
  - Automatic media detection
  - **Scan before download** - Preview what's available
  - **gallery-dl integration** - Enhanced downloading for supported sites

- **GUI Interface**: Easy-to-use tabbed interface for managing sources and downloads

- **Active/Inactive Management**: Organize sources into active (will scrape) and inactive (skip) lists:
  - Move items between lists without deleting
  - Only active items are scraped
  - Perfect for rotating sources or seasonal content

- **100% Duplicate Detection**: SHA256 file hashing guarantees no duplicates:
  - Works even if you move or rename files
  - Tracks both URL and file content hashes
  - Scan existing files to add to database

- **Progress Tracking**: Visual progress bar showing download status (e.g., "downloading 1/2000")

- **Discord Bot Integration**: Remote control your scraper through Discord:
  - Send commands from your Discord server (!scan, !scrapeall, !adduser, etc.)
  - Receive notifications when scraping starts/completes
  - Monitor progress updates directly in Discord

- **Smart History Tracking**: Remembers what's been downloaded to avoid duplicates:
  - Only downloads new content on subsequent runs
  - Tracks Reddit posts, Twitter tweets, and website media URLs
  - View statistics and clear history from the Settings tab

- **Organized Downloads**: Media automatically organized into folders:
  - `Downloads/username` for user content
  - `Downloads/subreddit` for subreddit content
  - `Downloads/domain_name` for website content

## Setup

### 1. Install Dependencies

```powershell
pip install -r botfiles/requirements.txt
```

Or navigate to the directory:
```powershell
cd "Downloading Software\Scraper"
pip install -r botfiles/requirements.txt
```

### 2. Configure API Credentials

#### Reddit OAuth Setup:
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" as the app type
4. Fill in the details and submit
5. Copy the Client ID (under the app name) and Client Secret

#### Twitter API Setup (Optional):
1. Go to https://developer.twitter.com/
2. Apply for a developer account
3. Create a new app
4. Generate API keys and bearer token

### 3. Run the Application

**Option 1: Double-click the batch file**
```
run_scraper.bat
```

**Option 2: Run from command line**
```powershell
python main.py
```

**Option 3: Run the GUI module directly**
```powershell
python -m botfiles.gui
```

## Usage

### Settings Tab
1. Open the application
2. Go to the "Settings" tab
3. Enter your Reddit API credentials:
   - Client ID
   - Client Secret
   - User Agent (e.g., "MediaScraper/1.0")
4. (Optional) Enter Twitter API credentials
5. Set your download path
6. Click "Save Settings"

### Reddit Tab

**Subreddits:**
1. Type a subreddit name (without r/)
2. Click "Add" to add it to the list
3. Click "Scrape All" to download media from all subreddits

**Reddit Users:**
1. Type a Reddit username (without u/)
2. Click "Add" to add it to the list
3. Click "Scrape All" to download media from all users

### Twitter Tab
1. Type a Twitter username (without @)
2. Click "Add" to add it to the list
3. Click "Scrape All" to download media from all users

### Websites Tab

**Basic Usage:**
1. Enter a website URL or sitemap.xml URL
2. **Optional**: Add a space after the URL followed by a custom folder name
   - Example: `https://example.com/user/john John`
   - This will save downloads to `Downloads/John/` instead of `Downloads/example.com/`
3. Click "Add" to add it to the list
4. Click "Scrape All" to scrape all websites

**Advanced Features:**

**Scan Before Download:**
1. Add a website/sitemap URL to your list
2. Select it in the list
3. Click "Scan Selected"
4. View preview of available media:
   - For sitemaps: See total URLs, pages, images, videos
   - For websites: See image/video counts, gallery-dl support status
5. After reviewing, click "Scrape All" to download

**Download with gallery-dl:**
1. Add a URL from a supported site (Reddit, Twitter, Instagram, etc.)
2. Select it in the list
3. Click "Download with gallery-dl"
4. gallery-dl will handle complex downloads including:
   - Video files with audio
   - Photo galleries
   - Multi-page albums
   - Site-specific optimizations

### Discord Bot (Remote Control)

**Setup:**
1. Create a Discord bot:
   - Go to https://discord.com/developers/applications
   - Click "New Application" and give it a name
   - Go to the "Bot" tab and click "Add Bot"
   - Copy the bot token (click "Reset Token" if needed)
   - Enable "Message Content Intent" under Privileged Gateway Intents
2. Invite bot to your server:
   - Go to OAuth2 > URL Generator
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Read Messages/View Channels`
   - Copy the generated URL and open it in your browser to invite the bot
3. Get your channel ID:
   - Enable Developer Mode in Discord (User Settings > Advanced)
   - Right-click on the channel where you want notifications
   - Click "Copy Channel ID"

**Configure in GUI:**
1. Go to Settings tab
2. Scroll to "Discord Bot Settings"
3. Check "Enable Discord Bot"
4. Paste your bot token
5. Paste your notification channel ID
6. Click "Save Settings"
7. Click "Start Bot" to launch the Discord bot

**Available Commands:**
- `!scan` - Scan all sources and show statistics
- `!scrapeall` - Start scraping all configured sources
- `!adduser <platform> <username>` - Add a user (e.g., `!adduser reddit spez`)
- `!addsubreddit <name>` - Add a subreddit (e.g., `!addsubreddit pics`)
- `!addsite <url> [folder_name]` - Add a website (e.g., `!addsite https://example.com MyFolder`)
- `!status` - Check bot status and last activity
- `!list` - Show all configured sources (subreddits, users, websites)
- `!help` - Display command help

**Features:**
- Receive notifications when scraping starts and completes
- Get progress updates at 25%, 50%, 75%, and 100%
- Control your scraper from anywhere (phone, desktop, etc.)
- View statistics and manage sources remotely

### Progress Tracking

The GUI now displays a visual progress bar during download operations:
- Shows "Downloading X/Y (Z%)" in the status bar
- Progress bar appears at the bottom right during operations
- Updates in real-time as each source is processed
- Automatically hides when operation completes

## File Structure

```
Scraper/
├── main.py                     # Main entry point (run this!)
├── run_scraper.bat             # Windows batch launcher
├── README.md                   # Full documentation
└── botfiles/                   # Bot module files
    ├── __init__.py             # Package initialization
    ├── gui.py                  # GUI application
    ├── reddit_scraper.py       # Reddit scraping logic
    ├── twitter_scraper.py      # Twitter scraping logic
    ├── website_scraper.py      # Website scraping logic
    ├── sitemap_scanner.py      # Sitemap scanner & gallery-dl
    ├── discord_bot.py          # Discord bot for remote control
    ├── user_manager.py         # Active/Inactive management
    ├── duplicate_checker.py    # 100% duplicate detection
    ├── history.py              # Download history tracker
    ├── utils.py                # Utility functions
    ├── config.json             # Configuration file (API keys)
    ├── users_status.json       # Active/Inactive lists (auto-created)
    ├── file_hashes.json        # File hash database (auto-created)
    ├── download_history.json   # Download history (auto-created)
    ├── requirements.txt        # Python dependencies
    └── docs/                   # Documentation files
        ├── DISCORD_SETUP.md
        ├── HISTORY_FEATURE.md
        ├── INSTRUCTIONS.md
        ├── NEW_FEATURES_GUIDE.md
        ├── PROGRESS_AND_DISCORD.md
        ├── PROJECT_STRUCTURE.md
        └── SCANNING_GUIDE.md
├── INSTRUCTIONS.md             # Quick start guide
├── HISTORY_FEATURE.md          # History tracking guide
├── SCANNING_GUIDE.md           # Scanning & gallery-dl guide
└── Downloads/                  # Downloaded media (auto-created)
    ├── username1/
    ├── subreddit1/
    └── domain_name/
```

## Configuration Files

All configuration files are located in the `botfiles/` directory.

### botfiles/usernames.txt
Add usernames in the format `platform:username`:
```
reddit:example_user
twitter:another_user
```

### botfiles/subreddit.txt
Add subreddit names (one per line):
```
pics
videos
gifs
```

### botfiles/websites.txt
Add website URLs or sitemap URLs. Optionally add a custom folder name after the URL:
```
https://example.com/sitemap.xml
https://example.com/gallery
https://nsfw.xxx/user/Penny_foryouthots Penny
https://example.com/user/john123 John
```
Format: `URL` or `URL CustomFolderName` (separated by space)

## Notes

- Media files are downloaded to `Downloads/` by default (configurable in settings)
- Files are organized by source (username, subreddit, or website domain)
- Duplicate files are automatically skipped
- The application runs scraping operations in background threads to keep the UI responsive
- Activity logs are shown in the Settings tab

## Troubleshooting

**Reddit scraper not working:**
- Verify your Client ID and Client Secret are correct
- Make sure you created a "script" type app on Reddit
- Check the activity log for specific error messages

**Twitter scraper not working:**
- Ensure you have valid Twitter API credentials
- Bearer token is preferred for API v2
- Note: Twitter API has rate limits

**Website scraper not finding media:**
- Some websites may block scrapers
- Ensure the URL is accessible
- Check if the website requires authentication

## Requirements

- Python 3.7+
- Internet connection
- Reddit API credentials (for Reddit scraping)
- Twitter API credentials (optional, for Twitter scraping)
- Discord bot token (optional, for Discord integration)

## License

This tool is for personal use only. Respect website terms of service and rate limits.
