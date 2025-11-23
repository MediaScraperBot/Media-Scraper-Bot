# Quick Start Guide

## ✅ Everything is Ready!

### Root Folder (Clean!)
```
d:\Downloading Software\Scraper\
├── main.py              ← Launch this!
├── run_scraper.bat      ← Or double-click this!
└── README.md            ← Full documentation
```

All code is in `botfiles/` folder, all docs in `botfiles/docs/`

---

## 🚀 Start Using Now

### 1. Install Dependencies
```powershell
pip install -r botfiles/requirements.txt
```

### 2. Launch the Application
```powershell
python main.py
```
Or double-click `run_scraper.bat`

### 3. Configure Settings
- Go to **Settings** tab
- Enter Reddit API credentials (see README.md for setup)
- Discord bot is already configured and ready!
- Click **Save Settings**

### 4. Start Discord Bot (Optional)
- Go to **Settings** tab
- Click **"Start Bot"**
- Test in Discord: `!help`

---

## 🎯 New Features You Have

### ✅ Active/Inactive Lists
**Every tab now has TWO lists:**
- **Green (Active)** = Will be scraped
- **Red (Inactive)** = Will be skipped

**Move items between lists:**
- Select item(s) and click → or ← buttons
- Only active items are scraped!

**Example:**
```
Reddit Tab:
[Active - Will scrape]     →  ←  [Inactive - Skip]
- wallpapers                      - memes
- pics                            - funny
```

### ✅ 100% Duplicate Detection
**Settings Tab → Duplicate Detection:**
- **Scan Existing Files** - Add all current downloads to database
- **View Hash Stats** - See tracked files and sizes
- **Migrate Old Data** - Import from old text files

**How it works:**
- SHA256 file hashing - mathematical guarantee
- Works even if you move/rename files
- Checks URL hash AND file content hash

### ✅ Discord Bot
**Already configured with your token!**
- Channel ID: 6674700557
- Commands: `!help`, `!scan`, `!scrapeall`, `!adduser`, etc.
- Start bot in Settings tab

---

## 📖 Quick Usage

### Add Items
1. Type in the entry box
2. Click "Add" - goes to Active list automatically
3. Repeat for all sources

### Move to Inactive (Pause without deleting)
1. Select items in Active list
2. Click → button
3. Items move to Inactive (won't be scraped)

### Move Back to Active
1. Select items in Inactive list
2. Click ← button
3. Items move back to Active

### Scrape Active Items
1. Click **"Scrape Active"** button
2. Only green (active) items are scraped
3. Watch progress bar at bottom!

---

## 🔐 Your Discord Bot is Ready

**Token:** Already added to `botfiles/config.json`
**Channel:** 6674700557
**Status:** Enabled

**To use:**
1. Settings tab → Click "Start Bot"
2. In Discord: `!help`
3. Try: `!status`, `!list`, `!scan`

---

## 📁 File Organization

### Config Files (all in botfiles/)
- `config.json` - API keys (Discord token already added!)
- `users_status.json` - Active/Inactive lists (auto-created)
- `file_hashes.json` - Duplicate detection database (auto-created)
- `download_history.json` - Download history (auto-created)

### Documentation (all in botfiles/docs/)
- `NEW_FEATURES_GUIDE.md` - Detailed feature guide
- `DISCORD_SETUP.md` - Discord bot setup (already done!)
- `INSTRUCTIONS.md` - Usage instructions
- And more...

---

## 🎉 What You Can Do Right Now

1. **Run the app:** `python main.py`
2. **Add some subreddits/users** to Active lists
3. **Click "Scrape Active"** - only active items scraped!
4. **Move items to Inactive** anytime to pause them
5. **Start Discord bot** - control remotely!
6. **Scan existing files** - add to duplicate database

---

## 💡 Tips

- **Testing?** Move most items to Inactive, keep 1 Active
- **Seasonal content?** Inactive in off-season, Active when needed
- **Rotate sources?** Keep favorites Active, rotate others
- **Moved files?** Duplicate checker still recognizes them!
- **Discord commands** work even when GUI is running

---

## 🆘 Need Help?

- Full docs: `README.md`
- Feature guide: `botfiles/docs/NEW_FEATURES_GUIDE.md`
- Discord setup: `botfiles/docs/DISCORD_SETUP.md`
- Activity log in Settings tab shows what's happening

---

**Everything is installed, configured, and ready to use!** 🚀

Just run `python main.py` and start scraping!
