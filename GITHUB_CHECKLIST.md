# 📋 GitHub Publishing Checklist

Before pushing to GitHub, verify these items:

## ✅ Files Included (Public)

- [x] `main.py` - Entry point
- [x] `Launch Media Scraper.bat` - Windows launcher
- [x] `README.md` - Main documentation
- [x] `SETUP.md` - First-time setup guide
- [x] `LICENSE` - MIT License
- [x] `THIRD_PARTY.md` - OF-DL info
- [x] `.gitignore` - Protects sensitive data
- [x] `botfiles/` - All Python modules
- [x] `botfiles/requirements.txt` - Dependencies
- [x] `botfiles/*.template` - Template config files

## ⛔ Files Excluded (Private/Ignored)

These files are in `.gitignore` and will NOT be uploaded:

- [x] `botfiles/config.json` - **YOUR API CREDENTIALS**
- [x] `botfiles/download_history.json` - Your download history
- [x] `botfiles/download_queue.json` - Your queue
- [x] `botfiles/file_hashes.json` - Your file hashes
- [x] `botfiles/subreddit.txt` - Your subreddit list
- [x] `botfiles/usernames.txt` - Your username list
- [x] `botfiles/websites.txt` - Your website list
- [x] `botfiles/scraper_activity.log` - Your logs
- [x] `Downloads/` - **YOUR DOWNLOADED CONTENT**
- [x] `.venv/` - Virtual environment
- [x] `__pycache__/` - Python cache

## 🔍 Pre-Upload Verification

### Step 1: Check Git Status
```bash
git status
```

Make sure you see:
- ✅ Only template files (*.template)
- ✅ No config.json (only config.json.template)
- ✅ No personal data files

### Step 2: Test .gitignore
```bash
# This should show NO sensitive files
git status --ignored

# If you see config.json or Downloads/, they're protected ✓
```

### Step 3: Verify Templates Exist
```bash
dir botfiles\*.template
```

Should show:
- config.json.template
- subreddit.txt.template
- usernames.txt.template
- websites.txt.template

### Step 4: Test Clean Clone
```bash
# In a different folder, test the setup process
git clone your-repo-url test-clone
cd test-clone
python -m venv .venv
.venv\Scripts\activate
pip install -r botfiles/requirements.txt
python main.py
```

Should:
- ✅ Create config files from templates
- ✅ Show "Configure API credentials" message
- ✅ Launch GUI without errors
- ⛔ NOT have your API keys

## 📤 GitHub Upload Commands

### First Time (New Repository)

```bash
# Initialize Git
git init

# Add all files (respects .gitignore)
git add .

# Check what will be committed
git status

# Commit
git commit -m "Initial commit: Media Scraper Bot v1.0"

# Create GitHub repo at: https://github.com/new

# Link to GitHub (replace with your URL)
git remote add origin https://github.com/yourusername/media-scraper-bot.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Updating Existing Repository

```bash
# Check status
git status

# Add changes
git add .

# Commit with message
git commit -m "Update: Add API help buttons and security improvements"

# Push to GitHub
git push
```

## 🔒 Security Double-Check

Before pushing, manually verify:

1. **Open `.gitignore`**
   - Confirm `botfiles/config.json` is listed
   - Confirm `Downloads/` is listed

2. **Check config.json.template**
   - Should have placeholders like `YOUR_REDDIT_CLIENT_ID_HERE`
   - Should NOT have your real credentials

3. **Search for Credentials**
   ```bash
   # Search for your real Reddit Client ID (example)
   git grep -i "3m0Ss-YW_PxanS2APjoIFg"
   
   # Should return: No results or only in gitignored files
   ```

4. **View Files to be Committed**
   ```bash
   git diff --cached --name-only
   ```
   
   Should NOT include:
   - config.json (without .template)
   - Any files in Downloads/
   - Any .log files with your data

## 🎯 Post-Upload Tasks

After pushing to GitHub:

1. **Test the Setup Guide**
   - Clone your repo in a fresh location
   - Follow SETUP.md step-by-step
   - Verify templates are copied correctly

2. **Update Repository Settings**
   - Add description: "Media Scraper Bot - Download from Reddit, Twitter, and websites"
   - Add topics: `python`, `scraper`, `reddit`, `twitter`, `downloader`, `media`
   - Add license: MIT

3. **Create Release (Optional)**
   - Go to Releases → Create new release
   - Tag: `v1.0.0`
   - Title: "Media Scraper Bot v1.0"
   - Description: Feature list and requirements

4. **Add Badges to README**
   - Python version badge ✓ (already added)
   - License badge ✓ (already added)
   - Platform badge ✓ (already added)

## ⚠️ Emergency: Exposed Credentials

If you accidentally commit sensitive data:

### Option 1: Remove Last Commit (Not Pushed Yet)
```bash
git reset --soft HEAD~1
# Edit files to remove credentials
git add .
git commit -m "Fixed commit message"
```

### Option 2: Already Pushed to GitHub
1. **Immediately revoke ALL API credentials**
   - Reddit: Delete app at reddit.com/prefs/apps
   - Twitter: Regenerate all keys

2. **Remove from Git history**
   ```bash
   # Use git filter-branch or BFG Repo Cleaner
   # See: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
   ```

3. **Force push** (destroys history)
   ```bash
   git push --force
   ```

## 📧 Final Verification

Before making repository public:

- [ ] Verified .gitignore is working
- [ ] Tested clean clone in separate folder
- [ ] Confirmed no credentials in any file
- [ ] Tested template auto-copy feature
- [ ] API help buttons work correctly
- [ ] README is accurate and complete
- [ ] SETUP.md is clear for new users
- [ ] LICENSE file is present
- [ ] All links in README work

## 🎉 Ready to Publish!

Once all checks pass:

```bash
# Make sure you're on main branch
git branch

# Final push
git push origin main
```

Then on GitHub:
1. Go to repository Settings
2. Scroll to "Danger Zone"
3. Click "Change visibility" → "Public"
4. Confirm by typing repository name

**Congratulations!** Your project is now public! 🚀

---

**Keep Your Fork Secure:**
- Never commit to public repo directly with your credentials
- Always work in private fork with real credentials
- Only push sanitized code to public repo
