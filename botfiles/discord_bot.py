"""
Discord bot integration for remote control of the scraper
"""
import discord
from discord.ext import commands
import asyncio
import threading
import os
from .utils import TextFileManager, ConfigManager


class ScraperDiscordBot:
    """Discord bot for controlling the scraper remotely"""
    
    def __init__(self, gui_app=None):
        self.gui_app = gui_app
        self.bot = None
        self.bot_thread = None
        self.running = False
        self.loop = None
        
        # Get botfiles directory
        botfiles_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Initialize managers
        self.config = ConfigManager(os.path.join(botfiles_dir, 'config.json'))
        self.usernames_manager = TextFileManager(os.path.join(botfiles_dir, 'usernames.txt'))
        self.subreddit_manager = TextFileManager(os.path.join(botfiles_dir, 'subreddit.txt'))
        self.websites_manager = TextFileManager(os.path.join(botfiles_dir, 'websites.txt'))
    
    def create_bot(self):
        """Create the Discord bot instance"""
        intents = discord.Intents.default()
        intents.message_content = True
        
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        @self.bot.event
        async def on_ready():
            if not self.bot:
                return
            print(f'✅ Discord bot logged in as {self.bot.user}')
            print(f'📋 Bot is in {len(self.bot.guilds)} server(s)')
            
            # Log to GUI
            if self.gui_app:
                self.gui_app.log(f'✅ Discord bot connected as {self.bot.user}')
                self.gui_app.log(f'📋 Bot is in {len(self.bot.guilds)} server(s)')
            
            for guild in self.bot.guilds:
                print(f'   - {guild.name} (ID: {guild.id})')
                if self.gui_app:
                    self.gui_app.log(f'   Server: {guild.name} (ID: {guild.id})')
                
                # List first 10 text channels (deduplicate by name, keep first occurrence)
                text_channels = [c for c in guild.channels if hasattr(c, 'send')][:10]
                seen_names = set()
                for ch in text_channels:
                    if ch.name.lower() not in seen_names:
                        seen_names.add(ch.name.lower())
                        print(f'      • #{ch.name} (ID: {ch.id})')
                        if self.gui_app:
                            self.gui_app.log(f'      Channel: #{ch.name} (ID: {ch.id})')
            
            # Try to send connection notification to general channel
            general_channel = self.config.get('discord.general_channel_id')
            downloads_channel = self.config.get('discord.downloads_channel_id')
            if self.gui_app:
                self.gui_app.log(f'⚙️ General channel ID: {general_channel}')
                self.gui_app.log(f'⚙️ Downloads channel ID: {downloads_channel}')
            
            # Send welcome message with commands
            welcome_msg = """🤖 **Scraper Bot Online!**

**Quick Commands:**
• `!scan` - View current sources
• `!scrapeall` - Start scraping all sources
• `!status` - Get scraper status
• `!adduser <platform> <username>` - Add user
• `!addsubreddit <name>` - Add subreddit
• `!addsite <url> [folder]` - Add website
• `!list [type]` - List sources
• `!commands` - Full command list
• `!channelid` - Get channel ID for config

Type `!commands` for detailed help."""
            await self.send_notification(welcome_msg, channel_type='general')
        
        @self.bot.command(name='channelid')
        async def channelid(ctx):
            """Get the ID of the current channel for notifications"""
            channel_id = ctx.channel.id
            await ctx.send(f'📍 This channel ID is: `{channel_id}`\n'
                          f'To use this for notifications, update your config.json:\n'
                          f'**For general status updates (online/offline/progress):**\n'
                          f'```json\n"discord": {{\n  "general_channel_id": "{channel_id}"\n}}\n```\n'
                          f'**For download details (files downloaded, sizes, etc):**\n'
                          f'```json\n"discord": {{\n  "downloads_channel_id": "{channel_id}"\n}}\n```')
        
        @self.bot.command(name='scan')
        async def scan(ctx):
            """Scan configured sources"""
            await ctx.send('🔍 Starting scan...')
            if self.gui_app:
                # Trigger scan in GUI
                status = self.get_sources_status()
                await ctx.send(f'📊 **Current Sources:**\n{status}')
            else:
                await ctx.send('❌ GUI not connected')
        
        @self.bot.command(name='scrapeall')
        async def scrapeall(ctx):
            """Start scraping all sources"""
            await ctx.send('🚀 Starting scrape of all sources...')
            if self.gui_app:
                # Trigger scraping
                self.gui_app.root.after(0, self._trigger_scrape_all)
                await ctx.send('✅ Scraping started! Check the GUI for progress.')
            else:
                await ctx.send('❌ GUI not connected')
        
        @self.bot.command(name='adduser')
        async def adduser(ctx, platform: str, username: str):
            """Add a user to scrape. Usage: !adduser reddit john"""
            try:
                entry = f"{platform}:{username}"
                if self.usernames_manager.add_item(entry):
                    await ctx.send(f'✅ Added user: {platform}:{username}')
                    if self.gui_app:
                        self.gui_app.root.after(0, self._refresh_user_lists)
                else:
                    await ctx.send(f'⚠️ User already exists: {platform}:{username}')
            except Exception as e:
                await ctx.send(f'❌ Error: {str(e)}')
        
        @self.bot.command(name='addsubreddit')
        async def addsubreddit(ctx, subreddit: str):
            """Add a subreddit to scrape. Usage: !addsubreddit pics"""
            try:
                if self.subreddit_manager.add_item(subreddit):
                    await ctx.send(f'✅ Added subreddit: r/{subreddit}')
                    if self.gui_app:
                        self.gui_app.root.after(0, self.gui_app.refresh_subreddit_lists)
                else:
                    await ctx.send(f'⚠️ Subreddit already exists: r/{subreddit}')
            except Exception as e:
                await ctx.send(f'❌ Error: {str(e)}')
        
        @self.bot.command(name='addsite')
        async def addsite(ctx, url: str, *folder_name):
            """Add a website to scrape. Usage: !addsite https://example.com OR !addsite https://example.com FolderName"""
            try:
                entry = url
                if folder_name:
                    entry = f"{url} {' '.join(folder_name)}"
                
                if self.websites_manager.add_item(entry):
                    await ctx.send(f'✅ Added website: {entry}')
                    if self.gui_app:
                        self.gui_app.root.after(0, self.gui_app.refresh_website_list)
                else:
                    await ctx.send(f'⚠️ Website already exists')
            except Exception as e:
                await ctx.send(f'❌ Error: {str(e)}')
        
        @self.bot.command(name='status')
        async def status(ctx):
            """Get current scraper status"""
            status = self.get_sources_status()
            
            # Get download stats if available
            if self.gui_app and self.gui_app.download_history:
                stats = self.gui_app.download_history.get_statistics()
                status += f"\n\n📈 **Download History:**"
                status += f"\n• Reddit: {stats['total_reddit_posts']} posts tracked"
                status += f"\n• Twitter: {stats['total_twitter_tweets']} tweets tracked"
                status += f"\n• Websites: {stats['total_website_urls']} URLs tracked"
            
            await ctx.send(status)
        
        @self.bot.command(name='list')
        async def list_sources(ctx, source_type: str = 'all'):
            """List configured sources. Usage: !list [subreddits/users/websites/all]"""
            try:
                if source_type in ['subreddits', 'all']:
                    subreddits = self.subreddit_manager.read_items()
                    if subreddits:
                        await ctx.send(f"📋 **Subreddits ({len(subreddits)}):**\n" + "\n".join([f"• r/{s}" for s in subreddits[:20]]))
                
                if source_type in ['users', 'all']:
                    users = self.usernames_manager.read_items()
                    if users:
                        await ctx.send(f"👥 **Users ({len(users)}):**\n" + "\n".join([f"• {u}" for u in users[:20]]))
                
                if source_type in ['websites', 'all']:
                    websites = self.websites_manager.read_items()
                    if websites:
                        await ctx.send(f"🌐 **Websites ({len(websites)}):**\n" + "\n".join([f"• {w[:80]}" for w in websites[:20]]))
            except Exception as e:
                await ctx.send(f'❌ Error: {str(e)}')
        
        @self.bot.command(name='commands')
        async def help_cmd(ctx):
            """Show available commands"""
            help_text = """
🤖 **Scraper Bot Commands:**

**Scanning & Downloading:**
• `!scan` - View current sources
• `!scrapeall` - Start scraping all sources
• `!status` - Get scraper status and stats

**Adding Sources:**
• `!adduser <platform> <username>` - Add user (e.g., !adduser reddit john)
• `!addsubreddit <name>` - Add subreddit (e.g., !addsubreddit pics)
• `!addsite <url> [folder]` - Add website (e.g., !addsite https://example.com Folder)

**Viewing:**
• `!list [type]` - List sources (subreddits/users/websites/all)

**Other:**
• `!commands` - Show this help message
• `!channelid` - Get current channel ID
            """
            await ctx.send(help_text)
        
        return self.bot
    
    def get_sources_status(self):
        """Get status of all configured sources"""
        subreddits = self.subreddit_manager.read_items()
        users = self.usernames_manager.read_items()
        reddit_users = [u for u in users if u.startswith('reddit:')]
        twitter_users = [u for u in users if u.startswith('twitter:')]
        websites = self.websites_manager.read_items()
        
        status = "📊 **Configured Sources:**\n"
        status += f"• Subreddits: {len(subreddits)}\n"
        status += f"• Reddit Users: {len(reddit_users)}\n"
        status += f"• Twitter Users: {len(twitter_users)}\n"
        status += f"• Websites: {len(websites)}"
        
        return status
    
    def _trigger_scrape_all(self):
        """Trigger scraping in GUI"""
        if self.gui_app:
            # Trigger all scraping operations
            self.gui_app.scrape_all_subreddits()
    
    def _refresh_user_lists(self):
        """Refresh user lists in GUI"""
        if self.gui_app:
            self.gui_app.refresh_reddit_user_list()
            self.gui_app.refresh_twitter_user_list()
    
    async def send_notification(self, message, channel_type='general'):
        """Send a notification to Discord channel
        
        Args:
            message: The message to send
            channel_type: 'general' for status updates (online/offline/progress), 
                         'downloads' for download notifications (files, sizes, stats)
        """
        if self.bot and self.running:
            # Get appropriate channel from config
            if channel_type == 'downloads':
                channel_id = self.config.get('discord.downloads_channel_id')
                channel_name = 'downloads'
            else:
                channel_id = self.config.get('discord.general_channel_id')
                channel_name = 'general'
            
            if channel_id:
                try:
                    channel_id_int = int(str(channel_id))
                    channel = self.bot.get_channel(channel_id_int)
                    if channel and hasattr(channel, 'send'):
                        await channel.send(message)  # type: ignore
                        # Only log downloads channel messages in verbose mode
                        if channel_type == 'general' or not self.gui_app:
                            print(f"✅ Sent Discord {channel_type} notification to channel {channel_id}")
                    else:
                        error_msg = f"❌ {channel_name.capitalize()} channel {channel_id} not found!"
                        print(error_msg)
                        if self.gui_app:
                            self.gui_app.log(error_msg)
                            self.gui_app.log(f"💡 Use !channelid command in Discord to get correct channel ID")
                            available = [f"#{c.name} ({c.id})" for c in self.bot.get_all_channels() if hasattr(c, 'send')][:5]
                            if available:
                                self.gui_app.log(f"   Available channels: {', '.join(available)}")
                except ValueError as e:
                    error_msg = f"❌ Invalid {channel_name} channel ID '{channel_id}': {e}"
                    print(error_msg)
                    if self.gui_app:
                        self.gui_app.log(error_msg)
                except Exception as e:
                    error_msg = f"❌ Failed to send {channel_name} notification: {e}"
                    print(error_msg)
                    if self.gui_app:
                        self.gui_app.log(error_msg)
    
    async def send_download_notification(self, message):
        """Send download completion notification to downloads channel"""
        await self.send_notification(message, channel_type='downloads')
    
    async def send_progress_update(self, current, total):
        """Send progress update to Discord channel (only at key milestones)"""
        if self.bot and self.running and total > 0:
            # Send update at 25%, 50%, 75%, and 100%
            percentage = (current / total) * 100
            if percentage in [25, 50, 75, 100] or current == total:
                message = f"📊 Progress: {current}/{total} ({percentage:.0f}%)"
                await self.send_notification(message, channel_type='general')
    
    def start_bot(self, token):
        """Start the Discord bot in a separate thread"""
        if self.running:
            return
        
        self.create_bot()
        self.running = True
        self.loop = None
        
        def run_bot():
            # Create new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self._run_bot_async(token))
            except Exception as e:
                print(f"Discord bot error: {e}")
                self.running = False
            finally:
                self.loop.close()
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
    
    async def _run_bot_async(self, token):
        """Run the bot asynchronously"""
        try:
            if self.bot:
                await self.bot.start(token)
        except Exception as e:
            print(f"Discord bot error: {e}")
            self.running = False
    
    def stop_bot(self):
        """Stop the Discord bot"""
        if self.bot and self.running:
            asyncio.run_coroutine_threadsafe(self.bot.close(), self.bot.loop)
            self.running = False
    
    async def send_progress_message(self, message):
        """Send progress update to Discord"""
        await self.send_notification(message)
