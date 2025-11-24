# 🎬 Media Scraper Bot

A comprehensive media downloader with GUI for Reddit, Twitter/X, websites, and OnlyFans.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 💝 Support This Project

I work on this project in my free time. If you find it useful, consider buying me a coffee!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buy-me-a-coffee)](https://buymeacoffee.com/sknight)

**For updates or issues, contact:** MyMediaScraperBot@gmail.com

---

## ⚠️ LEGAL DISCLAIMER & TERMS OF USE

**READ CAREFULLY BEFORE USING THIS SOFTWARE**

### BY USING THIS SOFTWARE, YOU AGREE TO THE FOLLOWING TERMS:

#### 📚 Educational Purposes Only
This tool is provided for **educational and personal archival purposes only**.

#### 👤 User Responsibility & Liability
- **YOU** are solely responsible for how you use this software
- The creator assumes **NO LIABILITY** for any misuse, violations of terms of service, copyright infringement, or illegal activities
- **YOU** accept all legal consequences and risks of using this tool
- Using this software means **YOU** are liable, not the creator

#### ⚖️ Legal Compliance Required
You **MUST** comply with:
- All applicable laws and regulations in your jurisdiction
- Copyright laws and intellectual property rights
- Platform Terms of Service (Reddit, Twitter, OnlyFans, etc.)
- Website terms and conditions

**WARNING:** Unauthorized downloading of copyrighted content may be **ILLEGAL** in your jurisdiction.

#### 🚫 Prohibited Uses
Do **NOT** use this tool for:
- Downloading content without proper authorization or permission
- Circumventing copyright protection or DRM
- Violating platform Terms of Service
- Stalking, harassment, or privacy violations
- Distributing pirated or unauthorized content
- Any illegal activities

#### ⚠️ No Warranty
- This software is provided **"AS IS"** without any warranties or guarantees
- May stop working at any time due to API changes, platform updates, or policy changes
- No guarantee of functionality, reliability, or fitness for any purpose

#### 🔧 Third-Party Tools
- Integrates with third-party tools (OF-DL, gallery-dl, yt-dlp, Playwright)
- These are independently maintained and NOT created by this project
- We are **NOT** responsible for their functionality, legality, or updates

#### 🚨 Account Risks
- Using automated tools may violate platform Terms of Service
- Risk of account suspension, ban, or legal action
- **USE AT YOUR OWN RISK**

---

**BY DOWNLOADING, INSTALLING, OR USING THIS SOFTWARE, YOU ACKNOWLEDGE THAT YOU HAVE READ, UNDERSTOOD, AND AGREE TO THESE TERMS.**

**IF YOU DO NOT AGREE, DO NOT USE THIS SOFTWARE.**

---

## ✨ Features

- **Reddit Scraper**: Download from subreddits and user profiles with sorting options (hot/new/top/rising)
- **Twitter/X Scraper**: Download media from user timelines
- **Website Scraper**: Universal web scraper with Playwright rendering for JavaScript-heavy sites
- **OnlyFans Downloader**: Integrated OF-DL for authenticated downloads
- **Duplicate Detection**: SHA256-based duplicate checking across folders
- **Download Queue**: Persistent queue with retry logic
- **Auto-organize**: Categorize downloads by source type

## 📋 Requirements

- **Python 3.8+**
- **Windows OS** (tested on Windows 10/11)
- **gallery-dl** (automatically installed, no API needed for Reddit)
- **Twitter API credentials** (optional, paid tier recommended)

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
3. For Twitter: Click the **?** button for API setup instructions
4. For Reddit: No setup needed! Uses gallery-dl (click **?** for info)
5. Enter Twitter credentials (if using) and click **Save**

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

#### Reddit (No API Key Required!)
- Reddit scraping uses **gallery-dl** - no API credentials needed
- Works immediately after installation
- Can scrape public subreddits and user posts without authentication
- For more info, click the **?** button next to Reddit Settings in the app

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
│   ├── reddit_scraper.py      # Reddit scraper (uses gallery-dl)
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

- [gallery-dl](https://github.com/mikf/gallery-dl) - Universal media downloader (Reddit, image galleries)
- [Tweepy](https://www.tweepy.org/) - Twitter API wrapper
- [Playwright](https://playwright.dev/) - Browser automation
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloader
- [OF-DL](https://git.ofdl.tools/sim0n00ps/OF-DL) - OnlyFans downloader

## 📧 Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues first

---

Made with ❤️ for the scraping community
