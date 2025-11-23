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

**Optional but Recommended:**
```bash
# Install Playwright for JavaScript-heavy websites
playwright install chromium
```

### Step 4: First Launch

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

### Reddit API (Required for Reddit scraping)

1. **Go to Reddit Apps Page**
   - Visit: https://www.reddit.com/prefs/apps
   - Log in with your Reddit account

2. **Create Application**
   - Scroll down and click **"Create App"** or **"Create Another App"**
   
3. **Fill Out Form**
   - **Name:** `MediaScraper` (or any name you like)
   - **App type:** Select **"script"**
   - **Description:** Leave blank or add description
   - **About URL:** Leave blank
   - **Redirect URI:** `http://localhost:8080`

4. **Click "Create app"**

5. **Copy Credentials**
   - **Client ID:** Found under your app name (short string like `3m0Ss-YW_PxanS2APjoIFg`)
   - **Client Secret:** The "secret" field (longer alphanumeric string)
   - **User Agent:** Use format `YourAppName/1.0` (e.g., `MediaScraper/1.0`)

6. **Enter in Settings Tab**
   - Open Media Scraper Bot
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

### Discord Bot (Optional - For Remote Control)

1. **Create Discord Application**
   - Visit: https://discord.com/developers/applications
   - Click "New Application"
   - Give it a name

2. **Create Bot**
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the Bot Token

3. **Enable Intents**
   - Under "Bot" section
   - Enable **"Message Content Intent"**
   - Enable **"Server Members Intent"**

4. **Invite Bot to Server**
   - Go to "OAuth2" → "URL Generator"
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Read Message History`
   - Copy generated URL and open in browser
   - Select your server and authorize

5. **Get Channel IDs**
   - Enable Developer Mode in Discord (User Settings → Advanced)
   - Right-click channel → Copy ID
   - Get IDs for:
     - General channel (status updates)
     - Downloads channel (download notifications)

6. **Configure in Settings**
   - Paste Bot Token
   - Paste General Channel ID
   - Paste Downloads Channel ID
   - Enable "Auto-start bot on launch" if desired
   - Click **Save**

## 📁 OnlyFans Setup (Optional)

OnlyFans requires external tool: **OF-DL**

1. **Download OF-DL**
   - Visit: https://git.ofdl.tools/sim0n00ps/OF-DL/releases
   - Download latest `OF-DL.exe`

2. **Place in Folder**
   - Create folder: `C:\Tools\OF-DL\`
   - Place `OF-DL.exe` there

3. **Configure in Application**
   - Open Media Scraper Bot
   - Go to **OnlyFans** tab
   - Click **Browse** and select `OF-DL.exe`
   - Configure download options in **Settings** tab
   - Click **Launch OF-DL** when ready

See [THIRD_PARTY.md](THIRD_PARTY.md) for more details.

## ✅ Verification

Test your setup:

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

### "No module named 'praw'" or similar errors
```bash
# Reinstall dependencies
pip install -r botfiles/requirements.txt --force-reinstall
```

### Playwright errors
```bash
# Install Playwright browser
playwright install chromium
```

### "Access Denied" or permission errors
- Run as Administrator (right-click → Run as administrator)
- Check antivirus isn't blocking the app

### Reddit scraping fails
- Verify Client ID and Client Secret are correct
- Check User Agent matches format `AppName/1.0`
- Ensure Reddit account is in good standing

### Twitter scraping fails
- Verify all 5 credentials are entered correctly
- Free tier has severe rate limits (use paid tier)
- Check API key hasn't expired

## 📚 Next Steps

Now that you're set up:

1. **Read the README** - [README.md](README.md) for feature overview
2. **Explore the GUI** - Each tab has different functionality
3. **Check Duplicates Tab** - Manage duplicate files
4. **Try Discord Bot** - Control remotely (if configured)
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
