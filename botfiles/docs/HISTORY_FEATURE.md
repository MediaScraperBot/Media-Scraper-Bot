# Download History Feature

## What is it?

The scraper now includes a smart history tracking system that remembers what content has been downloaded. This prevents re-downloading the same media and makes subsequent runs much faster and more efficient.

## How it Works

### Automatic Tracking
When you scrape content, the bot automatically records:
- **Reddit**: Post IDs from subreddits and users
- **Twitter**: Tweet IDs from user timelines  
- **Websites**: Media URLs from web pages and sitemaps

### Smart Scanning
On the next run:
- The scraper checks each post/tweet/URL against the history
- Only NEW content is downloaded
- Already-seen content is skipped instantly
- You'll see messages like: "r/pics: 15 new posts, 85 already seen"

### History File
All history is saved in `download_history.json` which includes:
- Lists of all seen post/tweet IDs
- Media URLs from websites
- Timestamps of last updates for each source

## Benefits

✅ **Faster subsequent runs** - Skip already-seen content  
✅ **Save bandwidth** - Don't re-download the same files  
✅ **Efficient tracking** - Know exactly what's new  
✅ **Persistent memory** - History survives app restarts  

## Managing History

### View Statistics
1. Open the app
2. Go to **Settings** tab
3. Click **"View Statistics"**
4. See counts of tracked sources and items

### Clear History
If you want to re-download everything:
1. Go to **Settings** tab
2. Click **"Clear All History"**
3. Confirm the action
4. Next run will download everything again

### Manual Clearing
You can also delete or edit `download_history.json` manually if needed.

## Examples

### First Run
```
Scraping r/pics...
Scanning r/pics: Amazing sunset photo
Downloaded image123.jpg
Scanning r/pics: Cool cat picture  
Downloaded image124.jpg
...
Downloaded 50 files from r/pics
```

### Second Run (with history)
```
Scraping r/pics...
r/pics: 5 new posts, 45 already seen
Scanning r/pics: New landscape photo
Downloaded image125.jpg
...
Downloaded 5 files from r/pics
```

Much faster! Only processed the new content.

## Technical Details

### What Gets Tracked
- **Reddit Posts**: Unique post ID (e.g., "abc123")
- **Twitter Tweets**: Tweet ID number
- **Website URLs**: Full media URL

### When History is Saved
- After completing each subreddit/user/website
- Ensures progress is saved even if app crashes
- History file is updated incrementally

### Storage Format
JSON format for easy viewing/editing:
```json
{
  "reddit_posts": {
    "pics": ["post_id1", "post_id2", ...],
    "videos": ["post_id3", "post_id4", ...]
  },
  "twitter_tweets": {
    "username": ["tweet_id1", "tweet_id2", ...]
  },
  "websites": {
    "https://example.com": ["url1", "url2", ...]
  }
}
```

## Tips

💡 **Keep history enabled** for best performance  
💡 **Clear history** if you want to re-download from a source  
💡 **Check statistics** to see how much you've tracked  
💡 **History is automatic** - no configuration needed!
