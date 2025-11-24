# 🚀 Setup Guide - Media Scraper Bot

This guide will walk you through setting up the Media Scraper Bot from scratch.

## 📋 Prerequisites

- **Windows 10/11** (tested)
- **Python 3.8 or higher** ([Download Python](https://www.python.org/downloads/))
  - ✅ Check "Add Python to PATH" during installation
- **Git** ([Download Git](https://git-scm.com/downloads)) - Optional, for cloning

## 🔧 Installation Steps

### Step 1: Get the Code

**Option A: Git Clone (Recommended)**
```bash
git clone https://github.com/yourusername/media-scraper-bot.git
cd media-scraper-bot
```

**Option B: Download ZIP**
1. Click "Code" → "Download ZIP" on GitHub
2. Extract to your desired location
3. Open folder in Command Prompt or PowerShell

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Or activate it (Windows Command Prompt)
.venv\Scripts\activate.bat
```

### Step 3: Install Dependencies

```bash
# Install required Python packages
pip install -r botfiles/requirements.txt
```

### Step 4: Install Playwright Browsers (Required for Websites)

**⚠️ Important:** Many websites require JavaScript to load images/videos. Without this step, website scraping will be limited.

```bash
# Install Chromium browser for Playwright
playwright install chromium
```

This downloads the Chromium browser (~150MB) that Playwright uses to render JavaScript-heavy websites like:
- Instagram, Pinterest, Twitter/X
- Dynamic image galleries
- Sites with infinite scroll
- Video hosting sites

**Note:** This is separate from installing the `playwright` Python package. You need both!

### Step 5: First Launch

```bash
# Run the application
python main.py

# Or double-click: Launch Media Scraper.bat
```

On first launch, the application will:
- ✅ Create `config.json` from template
- ✅ Create `subreddit.txt` from template
- ✅ Create `usernames.txt` from template
- ✅ Create `websites.txt` from template
- ⚠️ Show message to configure API credentials

## 🔑 Getting API Credentials

### Reddit (No API Key Required! ✅)

Reddit scraping uses **gallery-dl** - no API credentials needed!

**How it works:**
- gallery-dl scrapes public Reddit content without authentication
- Works immediately after installation
- No setup required
- Can scrape public subreddits and user posts

**That's it!** Just enter a subreddit or username in the app and click Scrape.

For more information, click the **?** button next to Reddit Settings in the app.
   - Go to **Settings** tab
   - Paste Client ID, Client Secret, User Agent
   - Click **Save**

### Twitter API (Optional - Limited Free Tier)

⚠️ **Note:** Twitter's free API tier is very limited. Consider alternatives or paid tier.

1. **Apply for Developer Account**
   - Visit: https://developer.twitter.com/
   - Click "Sign up" and complete application
   - Wait for approval (usually instant to 24 hours)

2. **Create Project & App**
   - Go to Developer Portal
   - Create new Project
   - Create new App within the Project

3. **Generate API Keys**
   - Go to App → "Keys and tokens" tab
   - Click "Generate" for each credential type:
     - ✅ API Key & API Secret
     - ✅ Bearer Token
     - ✅ Access Token & Access Token Secret

4. **Enter in Settings Tab**
   - Paste all 5 credentials
   - Click **Save**

### Test Reddit
1. Go to **Reddit** tab
2. Click **Add Subreddit**
3. Enter: `funny`
4. Select from Active list
5. Click **Scrape All Subreddits**
6. Check `Downloads/subreddit/funny/` for media

### Test Twitter (if configured)
1. Go to **Twitter** tab
2. Add a Twitter username
3. Click **Scrape All Twitter Users**

### Test Website
1. Go to **Websites** tab
2. Add any URL with images/videos
3. Click **Scrape All Websites**

## 🐛 Troubleshooting

### Missing module errors
```bash
# Reinstall dependencies
pip install -r botfiles/requirements.txt --force-reinstall
```

### Playwright errors / Website scraping shows "using basic scraping"

**Problem:** Playwright package installed but browsers not downloaded

**Solution:**
```bash
# Install Chromium browser (required for JavaScript sites)
playwright install chromium
```

**Verify it worked:**
```bash
# Should show the browser path
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()"
```

### "Access Denied" or permission errors
- Run as Administrator (right-click → Run as administrator)
- Check antivirus isn't blocking the app

### Reddit scraping fails
- Ensure gallery-dl is installed: `pip install gallery-dl`
- Check if subreddit/user exists and is public
- For private content, you may need to configure cookies (see gallery-dl docs)
- Verify internet connection

### Twitter scraping fails
- Verify all 5 credentials are entered correctly
- Free tier has severe rate limits (use paid tier)
- Check API key hasn't expired

## 📚 Next Steps

Now that you're set up:

1. **Read the README** - [README.md](README.md) for feature overview
2. **Explore the GUI** - Each tab has different functionality
3. **Check Duplicates Tab** - Manage duplicate files
5. **Adjust Settings** - Customize download behavior

## 🆘 Getting Help

- **Check existing issues:** https://github.com/yourusername/media-scraper-bot/issues
- **Open new issue:** Provide error messages and steps to reproduce
- **Read documentation:** README.md, THIRD_PARTY.md

## 🔒 Security Reminder

- ⚠️ **Never share your `config.json`** - Contains API keys
- ⚠️ **Never commit credentials to Git** - Already in `.gitignore`
- ✅ **Use template files** when sharing project

---

**Happy Scraping! 🎉**
