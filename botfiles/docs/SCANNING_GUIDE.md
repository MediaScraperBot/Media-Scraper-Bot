# Sitemap Scanning and gallery-dl Integration

## Overview

The scraper now includes advanced features for scanning websites before downloading and using gallery-dl for enhanced downloads from supported sites.

## Features

### 1. Sitemap Scanning

**Scan sitemaps before downloading** to see what's available:

#### How to Use:
1. Add a sitemap URL to your websites list
   - Example: `https://example.com/sitemap.xml`
2. Select the sitemap in the list
3. Click **"Scan Selected"**
4. View the scan results:
   - Total URLs found
   - Number of page URLs
   - Number of image URLs
   - Number of video URLs

#### Benefits:
- ✅ Preview content before downloading
- ✅ See total file counts
- ✅ Verify sitemap is accessible
- ✅ Plan disk space requirements
- ✅ Works with nested sitemaps (sitemap indexes)

### 2. Website Content Preview

**Scan individual web pages** to preview media:

#### How to Use:
1. Add a website URL
   - Example: `https://example.com/gallery/user123`
2. Select it in the list
3. Click **"Scan Selected"**
4. View the scan results:
   - Number of images found
   - Number of videos found
   - Media links available
   - gallery-dl compatibility status

#### What Gets Detected:
- `<img>` tags (including lazy-loaded images)
- `<video>` tags and `<source>` elements
- Direct media links (`.jpg`, `.mp4`, etc.)
- gallery-dl support indicator

### 3. gallery-dl Integration

**Enhanced downloading** for supported websites using gallery-dl.

#### Supported Sites:
gallery-dl supports 100+ sites including:
- Reddit
- Twitter/X
- Instagram
- Imgur
- DeviantArt
- ArtStation
- Pixiv
- Tumblr
- And many more!

#### How to Use:
1. Add a URL from a supported site
   - Example: `https://www.reddit.com/user/username/submitted/`
   - Example: `https://twitter.com/username/media`
2. Select it in the list
3. Click **"Download with gallery-dl"**
4. gallery-dl will download all media

#### Advantages of gallery-dl:
- ✅ **Better video handling** - Gets videos with audio
- ✅ **Gallery support** - Downloads entire albums/galleries
- ✅ **Metadata** - Preserves post information
- ✅ **Site-specific optimizations** - Best quality downloads
- ✅ **Rate limiting** - Respects site limits automatically
- ✅ **Resume capability** - Can resume interrupted downloads

### 4. Deep Search

The scanner performs **deep searching** to find all media:

#### What "Deep Search" Means:
- Parses HTML for all image/video elements
- Checks `src`, `data-src`, `data-lazy` attributes
- Follows nested `<source>` tags in videos
- Scans all `<a>` links for media file extensions
- Checks sitemap indexes recursively

#### For Sitemaps:
- Finds nested sitemaps (sitemap of sitemaps)
- Extracts image URLs from `<image:image>` tags
- Extracts video URLs from `<video:video>` tags
- Processes all page URLs in sitemap

## Installation

### Install gallery-dl:
```powershell
pip install gallery-dl
```

Or update your requirements:
```powershell
pip install -r requirements.txt
```

### Verify Installation:
```powershell
gallery-dl --version
```

## Workflow Examples

### Example 1: Scan Sitemap → Download
```
1. Add: https://example.com/sitemap.xml CustomName
2. Click "Scan Selected"
3. See: "Found 500 pages, 2000 images, 50 videos"
4. Click "Scrape All" to download
5. Files save to: Downloads/CustomName/
```

### Example 2: Preview Website → Use gallery-dl
```
1. Add: https://www.reddit.com/user/photographer/submitted/ Photos
2. Click "Scan Selected"
3. See: "✓ gallery-dl supported"
4. Click "Download with gallery-dl"
5. gallery-dl downloads with best quality
6. Files save to: Downloads/Photos/
```

### Example 3: Check Support Before Download
```
1. Add any URL
2. Click "Scan Selected"
3. Check scan results:
   - If "gallery-dl supported" → Use gallery-dl button
   - If not supported → Use "Scrape All"
```

## Tips

### For Best Results:
- 🔍 **Always scan first** to preview what's available
- 📦 **Use gallery-dl** when supported for better quality
- 📁 **Use custom names** for organization (URL FolderName)
- 🔄 **History tracking** prevents re-downloads automatically

### For Large Sitemaps:
- Scanner limits to first 100 URLs to prevent overwhelming
- For full sitemap scraping, use "Scrape All" directly
- Check scan results to estimate total download size

### For Video-Heavy Sites:
- gallery-dl is MUCH better for videos
- Gets proper codecs and audio tracks
- Handles streaming video formats correctly

### Troubleshooting:
- **gallery-dl not found**: Run `pip install gallery-dl`
- **Scan shows 0 results**: Site may require authentication
- **Download fails**: Check if site blocks scrapers
- **Slow scanning**: Normal for large sitemaps

## Technical Details

### Scan Output Format:
```
Sitemap Scan:
- total_count: All URLs found
- page_urls: Regular web pages
- image_urls: Direct image URLs
- video_urls: Direct video URLs

Website Scan:
- images: <img> tag sources
- videos: <video> tag sources  
- links: <a> href to media files
- gallery_dl_supported: boolean
```

### gallery-dl Command:
The app runs gallery-dl with:
```bash
gallery-dl --destination <path> --no-part <url>
```

### Custom Folder Names:
When you use `URL FolderName` format:
- Scan shows: "Will save to: Downloads/FolderName/"
- Both scraping methods respect custom names
- Folder name is sanitized (removes invalid chars)

## FAQ

**Q: Should I scan every time?**
A: Not required, but helpful for new sources to see what's available.

**Q: Does scanning download anything?**
A: No, scanning only previews content without downloading.

**Q: Which is better: Scrape All or gallery-dl?**
A: Use gallery-dl for supported sites (better quality), Scrape All for others.

**Q: Can I scan multiple URLs at once?**
A: No, select one at a time to scan. But "Scrape All" processes all URLs.

**Q: What if gallery-dl fails?**
A: Fall back to "Scrape All" which uses standard web scraping.
