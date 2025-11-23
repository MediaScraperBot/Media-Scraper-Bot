# Discord Bot Setup Guide

This guide will help you set up Discord bot integration for remote control of your media scraper.

## Why Use Discord Bot?

- **Remote Control**: Send commands from your phone or any device with Discord
- **Notifications**: Get alerted when scraping starts/completes
- **Progress Updates**: Monitor download progress in real-time
- **Convenient Management**: Add sources and trigger scrapes without opening the GUI

## Step-by-Step Setup

### 1. Create a Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Enter a name (e.g., "Media Scraper Bot")
4. Click **"Create"**

### 2. Create the Bot

1. In your application, click **"Bot"** in the left sidebar
2. Click **"Add Bot"** and confirm
3. Under the bot's username, click **"Reset Token"** and then **"Copy"**
   - **⚠️ Important**: Save this token securely - you'll need it later
4. Scroll down to **"Privileged Gateway Intents"**
5. Enable **"Message Content Intent"** (required for reading commands)
6. Click **"Save Changes"**

### 3. Invite Bot to Your Server

1. Go to **"OAuth2"** > **"URL Generator"** in the left sidebar
2. Under **"Scopes"**, select:
   - ☑️ `bot`
3. Under **"Bot Permissions"**, select:
   - ☑️ `Send Messages`
   - ☑️ `Read Messages/View Channels`
   - ☑️ `Embed Links` (optional, for prettier messages)
4. Copy the generated URL at the bottom
5. Open the URL in your browser
6. Select your server and click **"Authorize"**

### 4. Get Your Channel ID

1. Open Discord and go to **User Settings** > **Advanced**
2. Enable **"Developer Mode"**
3. Go to your server and right-click the channel where you want notifications
4. Click **"Copy Channel ID"**
5. Save this ID - you'll need it for configuration

### 5. Configure in Scraper GUI

1. Run the scraper application: `python main.py`
2. Go to the **Settings** tab
3. Scroll to **"Discord Bot Settings"**
4. Enter the following:
   - **Enable Discord Bot**: Check the box
   - **Bot Token**: Paste the token from Step 2
   - **Notification Channel ID**: Paste the channel ID from Step 4
5. Click **"Save Settings"**
6. Click **"Start Bot"** button

### 6. Test the Bot

In your Discord channel, type:
```
!help
```

If the bot responds with a list of commands, it's working! 🎉

## Available Commands

Once the bot is running, you can use these commands in Discord:

### Information Commands
- `!help` - Display all available commands
- `!status` - Check bot status and last activity
- `!list` - Show all configured sources (subreddits, users, websites)

### Scraping Commands
- `!scan` - Scan all sources and show statistics (doesn't download)
- `!scrapeall` - Start scraping all configured sources

### Management Commands
- `!adduser <platform> <username>` - Add a user to scrape
  - Example: `!adduser reddit spez`
  - Example: `!adduser twitter elonmusk`
  
- `!addsubreddit <name>` - Add a subreddit to scrape
  - Example: `!addsubreddit pics`
  
- `!addsite <url> [folder_name]` - Add a website to scrape
  - Example: `!addsite https://example.com/gallery`
  - Example: `!addsite https://example.com/user/john John` (custom folder name)

## Notifications

The bot will automatically send notifications for:

- ✅ When scraping starts
- ✅ When scraping completes
- ✅ Progress updates (at 25%, 50%, 75%, and 100%)
- ✅ When new sources are added

## Troubleshooting

### Bot doesn't respond to commands

**Check these:**
1. Is "Message Content Intent" enabled in Discord Developer Portal?
2. Does the bot have permission to read and send messages in the channel?
3. Is the bot online in your server's member list?
4. Check the Activity Log in the Settings tab for error messages

### Bot goes offline

**Common causes:**
- Invalid bot token
- Network connection issues
- Bot token was regenerated (need to update in settings)

**Solution:**
1. Check the Activity Log in the GUI
2. Verify bot token is correct
3. Click "Start Bot" again if needed

### Commands work but no notifications

**Check:**
1. Is the Channel ID correct?
2. Does the bot have "Send Messages" permission in that channel?
3. Is "Enable Discord Bot" checked in settings?

**Test:**
Type `!status` - if the bot responds, it's working. Check channel permissions.

## Security Notes

⚠️ **Important Security Tips:**

1. **Never share your bot token** - It's like a password for your bot
2. If token is exposed, regenerate it immediately in Discord Developer Portal
3. Keep `config.json` private - it contains your bot token
4. Don't commit `config.json` to public repositories

## Example Workflow

Here's a typical usage scenario:

1. **Morning**: Check Discord on your phone
2. **Add new sources**: `!addsubreddit wallpapers`
3. **Start scraping**: `!scrapeall`
4. **Monitor**: Bot sends progress updates
5. **Done**: Bot notifies when complete
6. **Check results**: Open GUI on your computer to view downloads

## Advanced Usage

### Running Bot 24/7

To keep the bot running even when the GUI is closed:

1. The bot runs in a background thread
2. As long as the GUI application is running, the bot stays online
3. For true 24/7 operation, consider running the GUI on a server or always-on computer

### Multiple Notification Channels

Currently, the bot sends notifications to one channel. To use multiple channels:
1. Invite the bot to multiple channels in your server
2. Use commands in any channel (bot will respond there)
3. Notifications go to the configured channel ID in settings

## Getting Help

If you encounter issues:

1. Check the **Activity Log** in the Settings tab
2. Verify all configuration settings
3. Make sure Python packages are installed: `pip install -r botfiles/requirements.txt`
4. Test with `!help` command to verify bot connectivity

## Next Steps

Now that your Discord bot is set up:

- Try adding sources remotely: `!adduser reddit example`
- Monitor your scrapes: `!scrapeall` and watch the progress updates
- Check statistics anytime: `!scan`
- Add friends to your Discord server so they can use the bot too (if desired)

Enjoy controlling your media scraper from anywhere! 🤖
