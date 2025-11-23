# Website Scraping Resume Feature

## Overview
The website scraper now keeps a running history of which websites have been scraped and can resume from where it left off if interrupted.

## Features

### 1. **Progress Tracking**
- Tracks which websites have been fully processed
- Stores state in `botfiles/website_scrape_state.json`
- Persists between application restarts

### 2. **Resume Button**
- Located on the Websites tab next to "Scrape Active"
- Continues scraping from where it left off
- Skips already-completed websites
- Shows how many websites are remaining

### 3. **Clear State Button**
- Located on the Websites tab (🗑 Clear State)
- Resets the scraping progress
- Useful when you want to re-scrape all websites from scratch

## How to Use

### Starting a Fresh Scrape
1. Click **"Scrape Active"** button
   - This automatically clears any previous progress
   - Starts scraping all active websites from the beginning

### Resuming an Interrupted Scrape
1. Click **"▶ Resume"** button
   - Checks which websites have already been completed
   - Continues from the next unprocessed website
   - Shows progress: "X websites remaining, Y already completed"

### Resetting Progress
1. Click **"🗑 Clear State"** button
   - Clears the completion history
   - Next scrape will start from the beginning

## What Gets Tracked

The state file (`botfiles/website_scrape_state.json`) contains:
- **completed_websites**: Array of URLs that have been fully processed
- **current_website**: The website currently being scraped (or null if idle)

## Example Scenarios

### Scenario 1: Interrupted Scrape
```
You have 20 websites in your active list.
Scraping completes 12 websites, then crashes or you stop it.
Click "Resume" → It will skip the 12 completed websites and start from #13
```

### Scenario 2: All Complete
```
All websites have been scraped.
Click "Resume" → Shows dialog: "All websites have been scraped. Start fresh?"
Click Yes → Clears state and starts over
Click No → Does nothing
```

### Scenario 3: Adding New Websites
```
You scraped 10 websites yesterday.
Today you add 5 new websites to your active list.
Click "Resume" → Skips the 10 already-completed, scrapes only the 5 new ones
```

## Activity Log Messages

During scraping, you'll see these messages:

- `📋 Resume mode: Skipping X completed websites` - When using Resume button
- `✓ Completed: <url>` - When a website finishes scraping
- `📊 Session complete: X websites fully processed` - At the end of scraping
- `Cleared website scraping state` - When clicking Clear State button

## Download Queue Integration

The feature works seamlessly with the existing download queue:
- **Phase 1 (Discovery)**: Websites are scanned for media URLs
- **Phase 2 (Download)**: Media files are downloaded from the queue
- If you stop during Phase 1, resume will continue discovering new websites
- If you stop during Phase 2, the download queue persists and will resume automatically next time

## Technical Details

- State file location: `botfiles/website_scrape_state.json`
- Format: JSON with `completed_websites` array and `current_website` string
- State is saved after each website completes
- State is preserved even if the application crashes
- "Scrape Active" button always starts fresh (clears state)
- "Resume" button preserves and uses the state

## Benefits

1. **Resilient to interruptions** - Crashes, stops, or system restarts won't lose progress
2. **Saves time** - No need to re-scrape websites you've already processed
3. **Bandwidth efficient** - Avoid re-downloading discovery data
4. **Rate-limit friendly** - Can pause and resume without hitting API limits
5. **Flexible workflow** - Can add new sites and only scrape those
