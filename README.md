# 🎬 Media Scraper Bot

A comprehensive media downloader with GUI for Reddit, Twitter/X, websites, and OnlyFans.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ⚠️ LEGAL DISCLAIMER

**FOR EDUCATIONAL PURPOSES ONLY.** By using this software, you agree:

- **User Responsibility**: You are solely responsible for how you use this tool. The creator assumes NO liability for any misuse, copyright infringement, or violations of Terms of Service.
- **Comply with Laws**: You must comply with all applicable laws and platform Terms of Service.
- **No Warranty**: Provided "AS IS" without guarantees. May stop working due to API changes.
- **Account Risks**: Automated tools may violate platform ToS and result in account suspension.
- **No Illegal Use**: Do not use for unauthorized downloading, copyright circumvention, harassment, or illegal activities.

**USE AT YOUR OWN RISK.** The creator is not liable for any consequences of using this software.

## ✨ Features

- **Reddit Scraper**: Download from subreddits and user profiles with sorting options (hot/new/top/rising)
- **Twitter/X Scraper**: Download media from user timelines
- **Website Scraper**: Universal web scraper with Playwright rendering for JavaScript-heavy sites
- **OnlyFans Downloader**: Integrated OF-DL for authenticated downloads
- **Duplicate Detection**: SHA256-based duplicate checking across folders
- **Discord Bot Integration**: Control scraping via Discord commands
- **Download Queue**: Persistent queue with retry logic
- **Auto-organize**: Categorize downloads by source type

## 📋 Requirements

- **Python 3.8+**
- **Windows OS** (tested on Windows 10/11)
- **Reddit API credentials** (free)
- **Twitter API credentials** (optional, paid tier recommended)
- **Discord Bot** (optional)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/media-scraper-bot.git
cd media-scraper-bot
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install required packages
pip install -r botfiles/requirements.txt

# Optional: Install Playwright for website scraping
playwright install chromium
```

### 3. Configure API Credentials

First time setup will create default config files.

**Option A: Use GUI (Recommended)**
1. Run `Launch Media Scraper.bat`
2. Go to **Settings** tab
3. Click the **?** button next to Reddit/Twitter API for instructions
4. Enter your credentials and click **Save**

**Option B: Manual Setup**
1. Copy template files:
   ```bash
   copy botfiles\config.json.template botfiles\config.json
   copy botfiles\subreddit.txt.template botfiles\subreddit.txt
   copy botfiles\usernames.txt.template botfiles\usernames.txt
   copy botfiles\websites.txt.template botfiles\websites.txt
   ```

2. Edit `botfiles/config.json` with your API credentials

### 4. Get API Credentials

#### Reddit API (Required for Reddit scraping)
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" type
4. Set redirect URI to: `http://localhost:8080`
5. Copy Client ID and Client Secret

#### Twitter API (Optional)
- Free tier is very limited
- Basic tier ($100/month) recommended for scraping
- Apply at: https://developer.twitter.com/

### 5. Run the Application

```bash
# Windows
Launch Media Scraper.bat

# Or run directly
python main.py
```

## 📖 Usage

### Reddit Tab
- Add subreddits or users to active lists
- Select sort order (hot/new/top/rising) and limit
- Click "Scrape All Subreddits" or "Scrape All Users"

### Twitter Tab
- Add Twitter usernames to active list
- Click "Scrape All Twitter Users"

### Websites Tab
- Add URLs (regular pages or sitemaps)
- Optional: Add custom folder name after URL (space-separated)
- Click "Scrape All Websites"

### OnlyFans Tab
- Download and configure OF-DL from: https://git.ofdl.tools/sim0n00ps/OF-DL
- Set exe path in Settings
- Launch OF-DL for authenticated downloads

### Duplicates Tab
- Scan for duplicate files across folders
- Move or delete duplicates
- Global sweep across entire Downloads folder

## 🛠️ Advanced Features

### Discord Bot Integration
1. Create Discord bot at: https://discord.com/developers/applications
2. Enable required intents (Message Content)
3. Add bot token and channel IDs to Settings
4. Use commands: `!scrapeall`, `!addsubreddit`, `!addsite`, etc.

### Download Queue
- Persistent queue survives crashes
- Automatic retry on failed downloads
- Progress tracking

### Duplicate Detection
- SHA256 file hashing
- Cross-folder duplicate detection
- Pre-download skip for known URLs
- Global sweep functionality

## 📁 Project Structure

```
media-scraper-bot/
├── main.py                    # Entry point
├── Launch Media Scraper.bat   # Windows launcher
├── botfiles/
│   ├── gui.py                 # Main GUI application
│   ├── reddit_scraper.py      # Reddit API scraper
│   ├── twitter_scraper.py     # Twitter API scraper
│   ├── website_scraper.py     # Generic website scraper
│   ├── duplicate_checker.py   # Duplicate detection system
│   ├── discord_bot.py         # Discord bot integration
│   ├── download_queue.py      # Download queue manager
│   └── requirements.txt       # Python dependencies
└── Downloads/                 # Downloaded media (gitignored)
```

## 🔒 Security Notes

- **Never commit `config.json`** with your real credentials
- All sensitive files are in `.gitignore`
- Use template files for distribution
- Keep API tokens private

## 🐛 Troubleshooting

**Playwright errors:**
```bash
playwright install chromium
```

**Import errors:**
```bash
pip install -r botfiles/requirements.txt
```

**Permission denied on queue file:**
- Close other instances of the scraper
- Check antivirus software

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## ⚠️ Full Legal Disclaimer

**FOR EDUCATIONAL AND PERSONAL ARCHIVAL PURPOSES ONLY.**

### User Responsibility
By using this software, you acknowledge and agree that:
- You are **solely responsible** for how you use this tool
- The creator assumes **NO liability** for any misuse, violations of Terms of Service, copyright infringement, or illegal activities conducted with this software
- You use this tool entirely **at your own risk**

### Legal Compliance
You must comply with:
- All applicable local, state, federal, and international laws
- Copyright and intellectual property laws
- Platform Terms of Service (Reddit, Twitter/X, OnlyFans, etc.)
- Website robots.txt and terms of use
- API rate limits and usage policies

### No Warranty
This software is provided **"AS IS"** without any warranties or guarantees:
- May stop working at any time due to API changes or platform updates
- No guarantee of functionality, accuracy, or reliability
- Third-party integrations (OF-DL, gallery-dl, yt-dlp, Playwright) are independently maintained

### Account & Legal Risks
Be aware that:
- Using automated scraping tools may violate platform Terms of Service
- May result in account suspension, bans, or legal action
- Downloading copyrighted content without permission may be illegal
- Circumventing access controls or paywalls may violate laws

### Prohibited Uses
**DO NOT** use this software for:
- Downloading content without proper authorization or permission
- Circumventing copyright protection or digital rights management
- Stalking, harassment, or invasion of privacy
- Distributing pirated or copyrighted content
- Any illegal activities or purposes
- Commercial use without proper licensing
- Violating anyone's rights or any applicable laws

### Third-Party Tools Disclaimer
This software integrates with third-party tools (OF-DL, gallery-dl, yt-dlp, Playwright):
- These are **not created or maintained** by this project
- We are **not responsible** for their functionality, legality, or security
- OF-DL specifically may stop working at any time due to OnlyFans API changes
- Users must comply with the terms and licenses of all third-party tools

### Acceptance of Terms
**BY USING THIS SOFTWARE, YOU ACKNOWLEDGE THAT YOU HAVE READ, UNDERSTOOD, AND AGREE TO THIS DISCLAIMER.**

**IF YOU DO NOT AGREE, DO NOT USE THIS SOFTWARE.**

The creator, contributors, and distributors of this software shall not be held liable for any damages, legal issues, or consequences arising from the use or misuse of this tool.

## 🙏 Acknowledgments

- [PRAW](https://praw.readthedocs.io/) - Reddit API wrapper
- [Tweepy](https://www.tweepy.org/) - Twitter API wrapper
- [Playwright](https://playwright.dev/) - Browser automation
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloader
- [gallery-dl](https://github.com/mikf/gallery-dl) - Image gallery downloader
- [OF-DL](https://git.ofdl.tools/sim0n00ps/OF-DL) - OnlyFans downloader

## 📧 Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues first

---

Made with ❤️ for the scraping community
