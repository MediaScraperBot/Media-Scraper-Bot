# How to Fix HTTP 401 & 403 Errors

## What Changed

I've upgraded your Media Scraper to handle websites that require authentication. The scraper now includes:

### ✅ Improved Default Headers
Your scraper now mimics a real browser with complete headers:
- **User-Agent**: Updated to Chrome 120 (latest)
- **Accept headers**: Proper content type acceptance
- **Accept-Language**: English (US/international)
- **Browser security headers**: Sec-Fetch-Dest, Sec-Fetch-Mode, etc.

### ✅ Custom Authentication Settings (NEW!)
A new section in **Settings Tab → Website Authentication** allows you to add:
- **Cookies**: For sites requiring login (HTTP 401 errors)
- **Custom Headers**: For CDNs and APIs (HTTP 403 errors)

---

## 🔧 How to Fix Your Current Errors

### HTTP 401 (Unauthorized) - cinema-dell.noortg.com
This error means the site requires login cookies.

**Steps to fix:**

1. **Log into the website** in your browser (Chrome/Firefox/Edge)

2. **Get your cookies:**
   - Press **F12** to open Developer Tools
   - Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
   - In left panel, expand **Cookies**
   - Click on the website domain
   - Copy important cookie values (look for: `session`, `auth`, `token`, `user_id`)

3. **Add cookies to scraper:**
   - Open your scraper
   - Go to **Settings** tab
   - Scroll to **Website Authentication** section
   - In the **Cookies** box, paste:
     ```
     session_id=YOUR_VALUE; auth_token=YOUR_VALUE; user_id=YOUR_VALUE
     ```
   - Click **Save Settings**

4. **Try scraping again** - the 401 errors should be gone!

---

### HTTP 403 (Forbidden)
Some sites block requests that don't look like real browsers.

**Already fixed with improved headers!** Try scraping again and most 403 errors should disappear.

If they persist:
- Click the **?** button next to "Website Authentication" for advanced solutions
- May need to add `Referer` header pointing to the site

---

## 📖 Detailed Help

Click the **? button** next to **Website Authentication** in Settings for:
- Step-by-step screenshots
- How to find cookies in different browsers
- Custom header examples
- Common error scenarios and solutions

---

## ⚠️ Important Notes

### Cookies Expire
- Cookies usually expire after days/weeks
- If you start getting 401 errors again, refresh your cookies
- Some sites require you to log in again periodically

### Terms of Service
- Only use cookies from YOUR OWN logged-in sessions
- This may violate some website Terms of Service
- Use responsibly and for personal use only

### Security
- **Never share your cookies publicly** - they contain your login information
- Store them safely in the Settings
- Your config.json is not shared on GitHub (it's in .gitignore)

---

## 🚀 Testing Your Fixes

1. Save your authentication settings
2. Go back to the Websites tab
3. Try scraping the problematic URLs again
4. Check the Activity Log for:
   - ✅ Success messages
   - ❌ Still getting errors? See the ? help button for troubleshooting

---

## Example Cookie Format

```
session_id=abc123xyz789; auth_token=def456uvw; user_id=12345; remember_me=true
```

**Format rules:**
- Separate multiple cookies with semicolons (`;`)
- Format: `cookie_name=value`
- No quotes around values
- Can be on one line or multiple lines

---

## Need More Help?

Reddit thread recommendations from r/webscraping:
- **Scrapy**: Full web scraping framework (Python)
- **Playwright**: What you already have! Handles JavaScript-heavy sites
- **Cheerio + Axios**: Node.js alternative
- **ScrapeGraphAI / Crawl4AI**: AI-powered scrapers

Your scraper already uses the best tools mentioned in that thread (Playwright, BeautifulSoup, requests, yt-dlp, gallery-dl). The missing piece was just authentication support - which you now have!
