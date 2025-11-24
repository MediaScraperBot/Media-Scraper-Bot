"""
GUI Application for Media Scraper Bot
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import asyncio
import os
import time
import json
from .utils import ConfigManager, TextFileManager
from .reddit_scraper import RedditScraper
from .twitter_scraper import TwitterScraper
from .website_scraper import WebsiteScraper
from .history import DownloadHistory
from .sitemap_scanner import SitemapScanner, GalleryDLDownloader
from .user_manager import UserManager
from .duplicate_checker import DuplicateChecker
from .download_queue import DownloadQueue


class ScraperGUI:
    """Main GUI application for the scraper bot"""

    def save_activity_log(self, log_path=None):
        """Save the activity log to a file."""
        if not log_path:
            log_path = os.path.join(self.botfiles_dir, 'scraper_activity.log')
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get('1.0', 'end'))
            self.log(f"Activity log saved to {log_path}")
        except Exception as e:
            self.log(f"Failed to save log: {e}")

    def scan_download_folders(self):
        """Scan download folders for video files and report presence/count."""
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        video_exts = ('.mp4', '.webm', '.mkv', '.mov', '.avi', '.flv')
        report = []
        if not os.path.exists(base_path):
            self.log(f"Download path does not exist: {base_path}")
            return
        for root, dirs, files in os.walk(base_path):
            video_files = [f for f in files if f.lower().endswith(video_exts)]
            if video_files:
                report.append(f"{root}: {len(video_files)} video(s) present")
            else:
                report.append(f"{root}: No videos found")
        # Save report to file
        report_path = os.path.join(self.botfiles_dir, 'video_scan_report.txt')
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report))
            self.log(f"Video scan report saved to {report_path}")
        except Exception as e:
            self.log(f"Failed to save video scan report: {e}")
        # Also show summary in log
        for line in report:
            self.log(line)
    
    def delete_empty_folders(self):
        """Delete all empty folders in a selected directory."""
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        
        # Let user choose the root folder to scan
        selected_path = filedialog.askdirectory(
            title="Select folder to scan for empty folders",
            initialdir=base_path
        )
        
        if not selected_path:
            return
        
        if not os.path.exists(selected_path):
            self.log(f"Selected path does not exist: {selected_path}")
            return
        
        # Confirm action
        result = messagebox.askyesno(
            "Delete Empty Folders",
            f"This will delete all empty folders in:\n{selected_path}\n\nContinue?",
            icon='warning'
        )
        if not result:
            return
        
        self.log(f"Scanning for empty folders in: {selected_path}")
        deleted_count = 0
        error_count = 0
        skipped_system = 0
        
        # Walk through directories bottom-up (to handle nested empty folders)
        for root, dirs, files in os.walk(selected_path, topdown=False):
            # Skip the base directory itself
            if root == selected_path:
                continue
            
            # Skip known Windows protected backup/system folders
            folder_name = os.path.basename(root)
            if folder_name.startswith('Backup - ') or 'System Volume Information' in root or '$RECYCLE.BIN' in root:
                skipped_system += 1
                continue
            
            # Check if directory is empty (no files and no subdirectories)
            try:
                if not os.listdir(root):  # Directory is completely empty
                    # Try normal deletion first
                    try:
                        os.rmdir(root)
                        self.log(f"Deleted empty folder: {os.path.relpath(root, selected_path)}")
                        deleted_count += 1
                    except PermissionError:
                        # Try using rmdir command with force
                        import subprocess
                        try:
                            result = subprocess.run(['rmdir', '/S', '/Q', root], 
                                                  capture_output=True, 
                                                  text=True, 
                                                  shell=True)
                            if result.returncode == 0:
                                self.log(f"Force deleted empty folder: {os.path.relpath(root, selected_path)}")
                                deleted_count += 1
                            else:
                                raise Exception(f"rmdir failed: {result.stderr}")
                        except Exception as e:
                            self.log(f"Error deleting {os.path.relpath(root, selected_path)}: Access Denied (system protected)")
                            error_count += 1
            except OSError as e:
                if 'WinError 5' in str(e) or 'Access is denied' in str(e):
                    self.log(f"Skipping protected folder: {os.path.relpath(root, selected_path)}")
                    error_count += 1
                else:
                    self.log(f"Error deleting {os.path.relpath(root, selected_path)}: {e}")
                    error_count += 1
        
        if deleted_count > 0:
            self.log(f"✓ Cleanup complete: {deleted_count} empty folders deleted")
        else:
            self.log("No empty folders found")
        
        if skipped_system > 0:
            self.log(f"ℹ Skipped {skipped_system} Windows system backup folders (cannot be deleted)")
        
        if error_count > 0:
            self.log(f"⚠ {error_count} errors occurred (protected system folders)")

    def organize_downloads(self):
        """Organize files in the base download folder into videos/images/gifs/others.
        Operates per top-level folder inside the base path. Updates duplicate tracker paths.
        """
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        if not os.path.exists(base_path):
            self.log(f"Download path does not exist: {base_path}")
            return

        video_exts = {'.mp4', '.webm', '.mkv', '.mov', '.avi', '.flv', '.m4v', '.wmv'}
        image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        gif_exts = {'.gif'}

        def classify(path: str) -> str:
            ext = os.path.splitext(path.lower())[1]
            if ext in gif_exts:
                return 'gifs'
            if ext in image_exts:
                return 'images'
            if ext in video_exts or ext in {'.m3u8', '.mpg', '.mpeg'}:
                return 'videos'
            return 'others'

        moved = 0
        skipped = 0
        errors = 0

        # Detect category structure (reddit/subreddit/website/twitter)
        category_dirs = {d.name: d.path for d in os.scandir(base_path) if d.is_dir() and d.name.lower() in {
            'reddit','subreddit','website','twitter'
        }}

        candidate_roots = []
        if category_dirs:
            # Each child dir inside category dirs is a collection root
            for cat_name, cat_path in category_dirs.items():
                for child in os.scandir(cat_path):
                    if child.is_dir():
                        candidate_roots.append(child.path)
        else:
            # Legacy flat structure
            for entry in os.scandir(base_path):
                if entry.is_dir():
                    candidate_roots.append(entry.path)

        for root_dir in candidate_roots:
            # Ensure subfolders exist
            for sub in ('videos', 'images', 'gifs', 'others'):
                try:
                    os.makedirs(os.path.join(root_dir, sub), exist_ok=True)
                except Exception:
                    pass

            for r, dnames, fnames in os.walk(root_dir):
                for fname in fnames:
                    src = os.path.join(r, fname)
                    # Skip if already inside a categorized subfolder
                    rel = os.path.relpath(src, root_dir)
                    if os.path.normpath(rel).split(os.sep)[0] in {'videos', 'images', 'gifs', 'others'}:
                        skipped += 1
                        continue
                    kind = classify(src)
                    dest_dir = os.path.join(root_dir, kind)
                    os.makedirs(dest_dir, exist_ok=True)

                    # Create destination path, handle name collisions
                    base_name, ext = os.path.splitext(fname)
                    dest = os.path.join(dest_dir, fname)
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(dest_dir, f"{base_name} ({counter}){ext}")
                        counter += 1
                    try:
                        import shutil
                        shutil.move(src, dest)
                        # Update duplicate tracker
                        try:
                            self.duplicate_checker.remove_file(src)
                            self.duplicate_checker.add_file(dest)
                        except Exception:
                            pass
                        moved += 1
                        if moved % 25 == 0:
                            self.log(f"Organized {moved} files so far...")
                    except Exception as e:
                        errors += 1
                        self.log(f"Failed to move {src}: {e}")

        # Handle loose files directly under base_path
        for fname in [f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))]:
            src = os.path.join(base_path, fname)
            kind = classify(src)
            dest_dir = os.path.join(base_path, kind)
            os.makedirs(dest_dir, exist_ok=True)
            base_name, ext = os.path.splitext(fname)
            dest = os.path.join(dest_dir, fname)
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(dest_dir, f"{base_name} ({counter}){ext}")
                counter += 1
            try:
                import shutil
                shutil.move(src, dest)
                try:
                    self.duplicate_checker.remove_file(src)
                    self.duplicate_checker.add_file(dest)
                except Exception:
                    pass
                moved += 1
            except Exception as e:
                errors += 1
                self.log(f"Failed to move {src}: {e}")

        self.log(f"Organize complete: moved {moved} file(s), skipped {skipped}, errors {errors}")
    
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 Media Scraper Bot")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        
        # Configure modern styling
        self.style = ttk.Style()
        self.current_theme = 'light'
        
        # Try to set window icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        # Get the botfiles directory path
        self.botfiles_dir = os.path.dirname(os.path.abspath(__file__))

        # Initialize managers with paths in botfiles directory
        botfiles_dir = self.botfiles_dir
        self.config = ConfigManager(os.path.join(botfiles_dir, 'config.json'))
        self.usernames_manager = TextFileManager(os.path.join(botfiles_dir, 'usernames.txt'))
        self.subreddit_manager = TextFileManager(os.path.join(botfiles_dir, 'subreddit.txt'))
        self.websites_manager = TextFileManager(os.path.join(botfiles_dir, 'websites.txt'))

        # Initialize shared download history in botfiles directory
        self.download_history = DownloadHistory(os.path.join(botfiles_dir, 'download_history.json'))
        
        # Initialize user manager for active/inactive users
        self.user_manager = UserManager(os.path.join(botfiles_dir, 'users_status.json'))
        
        # Auto-migrate from old text files if users_status.json is empty
        if not self.user_manager.get_all_users('reddit') and not self.user_manager.get_all_users('subreddits'):
            # Try to migrate from old files
            migrated = self.user_manager.migrate_from_old_files(
                usernames_file=os.path.join(botfiles_dir, 'usernames.txt'),
                subreddit_file=os.path.join(botfiles_dir, 'subreddit.txt'),
                websites_file=os.path.join(botfiles_dir, 'websites.txt')
            )
            if migrated > 0:
                print(f"✅ Auto-migrated {migrated} items from old text files to new system")
        
        # Initialize duplicate checker for 100% duplicate detection
        self.duplicate_checker = DuplicateChecker(os.path.join(botfiles_dir, 'file_hashes.json'))
        
        # Website scraping state for resume functionality
        self.website_scrape_state_file = os.path.join(botfiles_dir, 'website_scrape_state.json')
        self.website_scrape_state = self._load_website_scrape_state()
        
        # Initialize scrapers (will be created when needed)
        self.reddit_scraper = None
        self.twitter_scraper = None
        self.website_scraper = WebsiteScraper(history=self.download_history, aggressive_popup=True, duplicate_checker=self.duplicate_checker)
        
        # Initialize sitemap scanner and gallery-dl downloader
        self.sitemap_scanner = SitemapScanner()
        self.gallery_dl = GalleryDLDownloader()
        
        # Progress tracking
        self.current_progress = 0
        self.total_items = 0
        self.progress_label_var = tk.StringVar(value="Ready")
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Keyboard shortcuts
        self._setup_keyboard_shortcuts()
        
        # Create tabs
        self.create_instructions_tab()
        self.create_reddit_tab()
        self.create_twitter_tab()
        self.create_website_tab()
        self.create_onlyfans_tab()
        self.create_duplicates_tab()
        self.create_settings_tab()
        
        # Status bar frame
        status_frame = tk.Frame(root, bd=1, relief=tk.SUNKEN)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status text
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)
        self.progress_bar.pack_forget()  # Hide initially
        
        # Download progress
        self.is_downloading = False
        self.is_paused = False
        
        # Show disclaimer on first launch
        self.root.after(100, self._show_first_launch_disclaimer)
        
        # Log migration status after GUI is ready
        self.root.after(200, self._check_migration_status)

        # Auto-organize downloads at startup (if enabled)
        self.root.after(800, self._auto_organize_startup)
    
    def _show_first_launch_disclaimer(self):
        """Show legal disclaimer on first launch or when disclaimer_accepted is false"""
        try:
            disclaimer_accepted = self.config.get('app.disclaimer_accepted', False)
            
            if not disclaimer_accepted:
                disclaimer_text = """⚠️ LEGAL DISCLAIMER & TERMS OF USE

By using this software, you agree to the following:

• FOR EDUCATIONAL PURPOSES ONLY
  This tool is for educational and personal archival purposes.

• USER RESPONSIBILITY
  You are SOLELY responsible for how you use this software.
  The creator assumes NO liability for any misuse, violations of
  terms of service, copyright infringement, or illegal activities.

• COMPLY WITH LAWS & TERMS OF SERVICE
  You must comply with all applicable laws, copyright regulations,
  and platform Terms of Service (Reddit, Twitter, OnlyFans, etc.).
  Unauthorized downloading may be illegal in your jurisdiction.

• NO WARRANTY
  This software is provided "AS IS" without guarantees.
  It may stop working due to API changes or platform updates.

• THIRD-PARTY TOOLS
  Integrates with third-party tools (OF-DL, gallery-dl, yt-dlp).
  We are not responsible for their functionality or legality.

• ACCOUNT RISKS
  Using automated tools may violate platform Terms of Service
  and result in account suspension or legal action.

• NO ILLEGAL USE
  Do not use for: downloading without permission, circumventing
  copyright, stalking, harassment, or distributing pirated content.

═══════════════════════════════════════════════════════

Do you understand and accept these terms?

By clicking YES, you acknowledge that you have read, understood,
and agree to these terms. If you click NO, the application will close."""

                # Show disclaimer dialog
                result = messagebox.askyesno(
                    "Legal Disclaimer - Terms of Use",
                    disclaimer_text,
                    icon='warning'
                )
                
                if result:
                    # User accepted
                    self.config.set('app.disclaimer_accepted', True)
                    self.log("✓ Legal disclaimer accepted by user")
                else:
                    # User declined - close application
                    messagebox.showwarning(
                        "Application Closing",
                        "You must accept the terms of use to continue.\n\nThe application will now close."
                    )
                    self.root.quit()
                    self.root.destroy()
        except Exception as e:
            self.log(f"Error showing disclaimer: {e}")
    
    def _check_migration_status(self):
        """Check and log if data was migrated from old files"""
        stats = self.user_manager.get_statistics()
        total_items = sum(stat['total'] for stat in stats.values())
        if total_items > 0:
            self.log(f"📊 Loaded {total_items} items from storage")
            for platform, stat in stats.items():
                if stat['total'] > 0:
                    self.log(f"  {platform}: {stat['active']} active, {stat['inactive']} inactive")
    
    def create_instructions_tab(self):
        """Create instructions tab with usage guide"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📖 Instructions")
        
        # Create main container with padding and border
        container = tk.Frame(tab, highlightthickness=2, highlightbackground='#2c3e50', relief='solid')
        container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Create canvas and scrollbar for scrolling
        canvas = tk.Canvas(container, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=canvas.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Update window width when canvas is resized
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Instructions content
        content_frame = ttk.Frame(scrollable_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Title
        title = tk.Label(content_frame, text="🎬 Media Scraper Bot - User Guide", 
                        font=('TkDefaultFont', 16, 'bold'), fg='#2c3e50')
        title.pack(anchor='w', pady=(0, 20))
        
        # Legal Disclaimer
        disclaimer_frame = ttk.Frame(content_frame)
        disclaimer_frame.pack(fill='x', pady=(0, 20))
        
        disclaimer_title = tk.Label(disclaimer_frame, text="⚠️ LEGAL DISCLAIMER & TERMS OF USE", 
                                   font=('TkDefaultFont', 11, 'bold'), fg='#c0392b')
        disclaimer_title.pack(anchor='w', pady=(0, 5))
        
        disclaimer_text = """By using this software, you agree to the following terms:

• FOR EDUCATIONAL PURPOSES ONLY: This tool is provided for educational and personal archival purposes.

• USER RESPONSIBILITY: You are solely responsible for how you use this software. The creator assumes NO liability for any misuse, violations of terms of service, copyright infringement, or illegal activities conducted with this tool.

• COMPLY WITH LAWS & TERMS OF SERVICE: You must comply with all applicable laws, copyright regulations, and platform Terms of Service (Reddit, Twitter, OnlyFans, etc.). Unauthorized downloading of copyrighted content may be illegal in your jurisdiction.

• NO WARRANTY: This software is provided "AS IS" without any guarantees. It may stop working at any time due to API changes or platform updates.

• THIRD-PARTY TOOLS: This software integrates with third-party tools (OF-DL, gallery-dl, yt-dlp, Playwright) that are independently maintained. We are not responsible for their functionality or legality.

• ACCOUNT RISKS: Using automated tools may violate platform Terms of Service and result in account suspension or legal action. Use at your own risk.

• NO ILLEGAL USE: Do not use this tool for illegal purposes, including but not limited to: downloading content without permission, circumventing copyright protection, stalking, harassment, or distributing pirated content.

BY CONTINUING TO USE THIS SOFTWARE, YOU ACKNOWLEDGE THAT YOU HAVE READ, UNDERSTOOD, AND AGREE TO THESE TERMS. IF YOU DO NOT AGREE, UNINSTALL THIS SOFTWARE IMMEDIATELY."""
        
        disclaimer_label = tk.Label(disclaimer_frame, text=disclaimer_text, wraplength=800, justify='left', 
                                   fg='#e74c3c', font=('TkDefaultFont', 8), bg='#fadbd8', relief='solid', borderwidth=1, padx=10, pady=10)
        disclaimer_label.pack(fill='x', pady=(5, 0))
        
        # Welcome section
        welcome_text = """Welcome to Media Scraper Bot! This application helps you download media from multiple platforms with built-in duplicate detection and organization features."""
        welcome = tk.Label(content_frame, text=welcome_text, wraplength=800, justify='left', fg='#34495e')
        welcome.pack(anchor='w', pady=(15, 15))
        
        # Quick Start section
        self._add_section_header(content_frame, "🚀 Quick Start")
        quick_start = """1. Configure API Credentials (Settings tab)
   • Reddit: No API needed! Uses gallery-dl (click ? for info)
   • Twitter: Click the ? button for API setup instructions
   • Enter Twitter credentials and click Save
   
2. Add Content Sources
   • Reddit: Add subreddits or usernames
   • Twitter: Add Twitter/X usernames
   • Websites: Add any URL (regular pages or sitemaps)
   
3. Start Scraping
   • Select items from Active list
   • Click "Scrape All" button
   • Monitor progress in Activity Log"""
        self._add_text_block(content_frame, quick_start)
        
        # Reddit Tab section
        self._add_section_header(content_frame, "📱 Reddit Tab")
        reddit_text = """• Add Subreddits: Enter subreddit name (without r/) and click Add
• Add Users: Enter Reddit username and click Add
• Sorting Options: Choose hot/new/top/rising and set post limit
• Active/Inactive Lists: Move items between lists to control what gets scraped
• Scrape All: Downloads media from all active subreddits/users
• Skip Duplicates: Automatically detects and skips previously downloaded content"""
        self._add_text_block(content_frame, reddit_text)
        
        # Twitter Tab section
        self._add_section_header(content_frame, "🐦 Twitter/X Tab")
        twitter_text = """• Add Users: Enter Twitter username (with or without @)
• Active/Inactive Lists: Control which users to scrape
• Scrape All: Downloads media from user timelines
• Note: Free Twitter API is very limited - paid tier recommended"""
        self._add_text_block(content_frame, twitter_text)
        
        # Websites Tab section
        self._add_section_header(content_frame, "🌐 Websites Tab")
        websites_text = """• Add URLs: Enter any website URL
• Custom Folders: Add space + folder name after URL (e.g., "https://site.com CustomFolder")
• Sitemap Support: Automatically detects and scrapes XML sitemaps
• Playwright Rendering: Handles JavaScript-heavy sites with infinite scroll
• Resume Feature: Automatically resumes incomplete scraping sessions
• Scan Website: Preview how many media files will be downloaded
• Gallery-DL: Use for sites like Instagram, Twitter, etc. (requires gallery-dl installed)"""
        self._add_text_block(content_frame, websites_text)
        
        # OnlyFans Tab section
        self._add_section_header(content_frame, "💎 OnlyFans Tab")
        onlyfans_text = """• External Tool: Uses OF-DL (third-party, not created by us)
• Download OF-DL: https://git.ofdl.tools/sim0n00ps/OF-DL/releases
• Setup: Browse to OF-DL.exe location and save
• Configuration: Set download options in Settings tab
• Launch: Click "Open OF-DL" to start authenticated downloads
• OF-DL handles login via browser for better security

⚠️ DISCLAIMER: OF-DL may stop working if OnlyFans changes their API or security.
For direct API access (advanced users), click the "Show OnlyFans API Instructions" button in the OnlyFans tab."""
        self._add_text_block(content_frame, onlyfans_text)
        
        # Duplicates Tab section
        self._add_section_header(content_frame, "🔍 Duplicates Tab")
        duplicates_text = """• Scan Folder: Check a specific folder for duplicate files
• Drive Scan: Scan entire drive with filters (media only, non-media, etc.)
• Global Sweep: One-click duplicate check across entire Downloads folder
• SHA256 Hashing: Uses file content hashing (not filename) to detect duplicates
• Cross-Folder Detection: Finds duplicates even if files are in different folders
• Move or Delete: Options to handle found duplicates
• Pre-Download Skip: Automatically skips downloading known duplicates"""
        self._add_text_block(content_frame, duplicates_text)
        
        # Settings Tab section
        self._add_section_header(content_frame, "⚙️ Settings Tab")
        settings_text = """• API Credentials: Configure Twitter API credentials (Reddit uses gallery-dl, no API needed)
• Help Buttons (?): Click for setup instructions and information
• Download Path: Set where media files are saved
• OnlyFans Options: Configure what content types to download
• Auto-Organize: Automatically organize downloads by source on startup
• History Management: View stats and clear download history"""
        self._add_text_block(content_frame, settings_text)
        
        # Tips & Tricks section
        self._add_section_header(content_frame, "💡 Tips & Tricks")
        tips_text = """✓ Use Active/Inactive lists to temporarily disable sources without deleting
✓ Global Sweep finds duplicates across ALL folders in Downloads
✓ Pre-download duplicate checking saves bandwidth and time
✓ Website scraping automatically detects and handles sitemaps
✓ Playwright handles sites that require JavaScript (slower but thorough)
✓ Resume feature lets you continue interrupted website scraping
✓ Use custom folder names for better organization: "url FolderName"
✓ Activity Log (bottom panel) shows real-time progress and errors
✓ Save Activity Log with Ctrl+S for troubleshooting"""
        self._add_text_block(content_frame, tips_text)
        
        # Keyboard Shortcuts section
        self._add_section_header(content_frame, "⌨️ Keyboard Shortcuts")
        shortcuts_text = """Ctrl+S - Save Activity Log
Ctrl+T - Toggle Theme (Light/Dark)
Ctrl+O - Open Downloads Folder
F5 - Refresh Current Tab
Ctrl+Tab - Switch Between Tabs"""
        self._add_text_block(content_frame, shortcuts_text)
        
        # Troubleshooting section
        self._add_section_header(content_frame, "🔧 Troubleshooting")
        troubleshooting_text = """• No media downloading: Check API credentials in Settings tab
• Playwright errors: Run "playwright install chromium" in terminal
• Permission denied: Close other instances, check antivirus
• Twitter not working: Free tier is very limited, consider alternatives
• Duplicates not detected: Ensure files haven't been modified (checks content hash)
• Website scraping incomplete: Use Resume feature or increase max pages
• OF-DL not working: Download latest version from official site"""
        self._add_text_block(content_frame, troubleshooting_text)
        
        # Donation section
        donation_frame = ttk.Frame(content_frame)
        donation_frame.pack(fill='x', pady=(30, 0))
        
        donation_text = tk.Label(donation_frame, 
                                text="💝 I work on this project in my free time. Any donations are welcome and appreciated!",
                                font=('TkDefaultFont', 11, 'bold'), fg='#27ae60', wraplength=800)
        donation_text.pack(anchor='w', pady=(0, 10))
        
        # Buy Me a Coffee button
        coffee_button = tk.Button(donation_frame, 
                                 text="☕ Buy Me a Coffee",
                                 font=('TkDefaultFont', 11, 'bold'),
                                 bg='#FFDD00', fg='#000000',
                                 activebackground='#FFCC00', activeforeground='#000000',
                                 relief='raised', bd=3, padx=30, pady=12,
                                 cursor='hand2',
                                 command=lambda: self._open_donation_link())
        coffee_button.pack(anchor='w', pady=(0, 15))
        
        # Contact button
        contact_button = tk.Button(donation_frame, 
                                  text="📧 For updates or issues, contact: MyMediaScraperBot@gmail.com",
                                  font=('TkDefaultFont', 10),
                                  bg='#3498db', fg='white',
                                  activebackground='#2980b9', activeforeground='white',
                                  relief='raised', bd=2, padx=20, pady=10,
                                  cursor='hand2',
                                  command=lambda: self._copy_email_to_clipboard())
        contact_button.pack(anchor='w', pady=(0, 10))
        
        # Footer
        footer = tk.Label(content_frame, 
                         text="For more help, check README.md and SETUP.md in the installation folder",
                         font=('TkDefaultFont', 9, 'italic'), fg='#7f8c8d')
        footer.pack(anchor='w', pady=(20, 10))
    
    def _add_section_header(self, parent, text):
        """Add a section header to instructions"""
        header = tk.Label(parent, text=text, font=('TkDefaultFont', 12, 'bold'), 
                         fg='#2980b9', anchor='w')
        header.pack(anchor='w', pady=(15, 5))
    
    def _add_text_block(self, parent, text):
        """Add a text block to instructions"""
        label = tk.Label(parent, text=text, wraplength=800, justify='left', 
                        fg='#2c3e50', anchor='w')
        label.pack(anchor='w', pady=(0, 10))
    
    def create_reddit_tab(self):
        """Create Reddit scraping tab with Active/Inactive lists"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reddit")
        
        # Subreddits section
        subreddit_frame = ttk.LabelFrame(tab, text="Subreddits", padding=10)
        subreddit_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Dual listbox layout (Active | Inactive)
        lists_frame = ttk.Frame(subreddit_frame)
        lists_frame.pack(fill='both', expand=True)
        
        # Active list
        active_frame = ttk.Frame(lists_frame)
        active_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        ttk.Label(active_frame, text="Active (Will be scraped)", font=('TkDefaultFont', 9, 'bold')).pack()
        active_scroll = ttk.Scrollbar(active_frame)
        active_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.subreddit_active_listbox = tk.Listbox(active_frame, yscrollcommand=active_scroll.set, height=6,
                                                     bg='#e8f5e9', selectmode=tk.EXTENDED)
        self.subreddit_active_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        active_scroll.config(command=self.subreddit_active_listbox.yview)
        
        # Middle buttons
        middle_frame = ttk.Frame(lists_frame)
        middle_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(middle_frame, text="").pack()  # Spacer
        ttk.Button(middle_frame, text="→", width=3, command=lambda: self.move_subreddit_to_inactive()).pack(pady=2)
        ttk.Button(middle_frame, text="←", width=3, command=lambda: self.move_subreddit_to_active()).pack(pady=2)
        
        # Inactive list
        inactive_frame = ttk.Frame(lists_frame)
        inactive_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(5, 0))
        
        ttk.Label(inactive_frame, text="Inactive (Skipped)", font=('TkDefaultFont', 9, 'bold')).pack()
        inactive_scroll = ttk.Scrollbar(inactive_frame)
        inactive_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.subreddit_inactive_listbox = tk.Listbox(inactive_frame, yscrollcommand=inactive_scroll.set, height=6,
                                                       bg='#ffebee', selectmode=tk.EXTENDED)
        self.subreddit_inactive_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        inactive_scroll.config(command=self.subreddit_inactive_listbox.yview)
        
        # Sorting options
        sort_frame = ttk.Frame(subreddit_frame)
        sort_frame.pack(fill='x', pady=5)
        
        ttk.Label(sort_frame, text="Sort by:").pack(side=tk.LEFT, padx=(0, 5))
        self.subreddit_sort_var = tk.StringVar(value="hot")
        sort_combo = ttk.Combobox(sort_frame, textvariable=self.subreddit_sort_var, width=12, state='readonly')
        sort_combo['values'] = ('hot', 'new', 'top', 'rising')
        sort_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(sort_frame, text="Limit:").pack(side=tk.LEFT, padx=(10, 2))
        self.subreddit_limit_var = tk.IntVar(value=100)
        ttk.Spinbox(sort_frame, from_=10, to=1000, increment=10, textvariable=self.subreddit_limit_var, width=8).pack(side=tk.LEFT)
        self.subreddit_unlimited_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sort_frame, text="⚡ Unlimited", variable=self.subreddit_unlimited_var).pack(side=tk.LEFT, padx=(10, 0))
        
        # Date range filter
        date_frame = ttk.Frame(subreddit_frame)
        date_frame.pack(fill='x', pady=5)
        
        ttk.Label(date_frame, text="Date Range Filter (optional):").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(date_frame, text="From:").pack(side=tk.LEFT, padx=(10, 2))
        self.subreddit_start_date = ttk.Entry(date_frame, width=12)
        self.subreddit_start_date.pack(side=tk.LEFT, padx=2)
        self.subreddit_start_date.insert(0, "YYYY-MM-DD")
        
        ttk.Label(date_frame, text="To:").pack(side=tk.LEFT, padx=(10, 2))
        self.subreddit_end_date = ttk.Entry(date_frame, width=12)
        self.subreddit_end_date.pack(side=tk.LEFT, padx=2)
        self.subreddit_end_date.insert(0, "YYYY-MM-DD")
        
        ttk.Label(date_frame, text="(leave blank for all posts)", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = ttk.Frame(subreddit_frame)
        btn_frame.pack(fill='x', pady=5)
        
        self.subreddit_entry = ttk.Entry(btn_frame)
        self.subreddit_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        
        ttk.Button(btn_frame, text="Add", command=self.add_subreddit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self.remove_subreddit).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Scrape Active", command=self.scrape_all_subreddits).pack(side=tk.LEFT, padx=2)
        
        # Pause/Resume button (shared across all scraping)
        self.pause_button = ttk.Button(btn_frame, text="⏸ Pause", command=self.toggle_pause, state='disabled')
        self.pause_button.pack(side=tk.LEFT, padx=2)
        
        # Reddit Users section
        user_frame = ttk.LabelFrame(tab, text="Reddit Users", padding=10)
        user_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Dual listbox layout (Active | Inactive)
        lists_frame2 = ttk.Frame(user_frame)
        lists_frame2.pack(fill='both', expand=True)
        
        # Active list
        active_frame2 = ttk.Frame(lists_frame2)
        active_frame2.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        ttk.Label(active_frame2, text="Active (Will be scraped)", font=('TkDefaultFont', 9, 'bold')).pack()
        active_scroll2 = ttk.Scrollbar(active_frame2)
        active_scroll2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.reddit_user_active_listbox = tk.Listbox(active_frame2, yscrollcommand=active_scroll2.set, height=6,
                                                       bg='#e8f5e9', selectmode=tk.EXTENDED)
        self.reddit_user_active_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        active_scroll2.config(command=self.reddit_user_active_listbox.yview)
        
        # Middle buttons
        middle_frame2 = ttk.Frame(lists_frame2)
        middle_frame2.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(middle_frame2, text="").pack()  # Spacer
        ttk.Button(middle_frame2, text="→", width=3, command=lambda: self.move_reddit_user_to_inactive()).pack(pady=2)
        ttk.Button(middle_frame2, text="←", width=3, command=lambda: self.move_reddit_user_to_active()).pack(pady=2)
        
        # Inactive list
        inactive_frame2 = ttk.Frame(lists_frame2)
        inactive_frame2.pack(side=tk.LEFT, fill='both', expand=True, padx=(5, 0))
        
        ttk.Label(inactive_frame2, text="Inactive (Skipped)", font=('TkDefaultFont', 9, 'bold')).pack()
        inactive_scroll2 = ttk.Scrollbar(inactive_frame2)
        inactive_scroll2.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.reddit_user_inactive_listbox = tk.Listbox(inactive_frame2, yscrollcommand=inactive_scroll2.set, height=6,
                                                         bg='#ffebee', selectmode=tk.EXTENDED)
        self.reddit_user_inactive_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        inactive_scroll2.config(command=self.reddit_user_inactive_listbox.yview)
        
        # Buttons
        btn_frame2 = ttk.Frame(user_frame)
        btn_frame2.pack(fill='x', pady=5)
        
        self.reddit_user_entry = ttk.Entry(btn_frame2)
        self.reddit_user_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        
        ttk.Button(btn_frame2, text="Add", command=self.add_reddit_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="Remove", command=self.remove_reddit_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="Scrape Active", command=self.scrape_all_reddit_users).pack(side=tk.LEFT, padx=2)
        
        # Post limit control
        limit_frame2 = ttk.Frame(user_frame)
        limit_frame2.pack(fill='x', pady=5)
        ttk.Label(limit_frame2, text="Posts to scan per user:").pack(side=tk.LEFT, padx=(0, 5))
        self.reddit_user_limit_var = tk.IntVar(value=100)
        ttk.Spinbox(limit_frame2, from_=10, to=1000, increment=10, textvariable=self.reddit_user_limit_var, width=10).pack(side=tk.LEFT)
        self.reddit_user_unlimited_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(limit_frame2, text="⚡ Scrape ALL posts (unlimited)", variable=self.reddit_user_unlimited_var).pack(side=tk.LEFT, padx=(15, 0))
        
        # Progress section
        progress_frame = ttk.LabelFrame(tab, text="Progress", padding=10)
        progress_frame.pack(fill='x', padx=10, pady=5)
        
        # Current operation label
        self.reddit_current_op_var = tk.StringVar(value="Ready to scrape...")
        current_op_label = ttk.Label(progress_frame, textvariable=self.reddit_current_op_var, 
                                     font=('TkDefaultFont', 9, 'bold'))
        current_op_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Progress bar
        self.reddit_progress_var = tk.IntVar(value=0)
        self.reddit_progress_bar = ttk.Progressbar(progress_frame, mode='determinate', 
                                                   variable=self.reddit_progress_var, length=400)
        self.reddit_progress_bar.pack(fill='x', pady=(0, 5))
        
        # Progress stats
        self.reddit_progress_text_var = tk.StringVar(value="0 / 0 items (0%)")
        progress_text_label = ttk.Label(progress_frame, textvariable=self.reddit_progress_text_var)
        progress_text_label.pack(anchor=tk.W)
        
        # Details label (for file counts, etc.)
        self.reddit_details_var = tk.StringVar(value="")
        details_label = ttk.Label(progress_frame, textvariable=self.reddit_details_var, 
                                 foreground='#666')
        details_label.pack(anchor=tk.W)
        
        # Load existing data
        self.refresh_subreddit_lists()
        self.refresh_reddit_user_lists()
    
    def create_twitter_tab(self):
        """Create Twitter scraping tab with Active/Inactive lists"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Twitter/X")
        
        # Twitter Users section
        user_frame = ttk.LabelFrame(tab, text="Twitter Users", padding=10)
        user_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Dual listbox layout (Active | Inactive)
        lists_frame = ttk.Frame(user_frame)
        lists_frame.pack(fill='both', expand=True)

        # Active list
        active_frame = ttk.Frame(lists_frame)
        active_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        ttk.Label(active_frame, text="Active (Will be scraped)", font=('TkDefaultFont', 9, 'bold')).pack()
        active_scroll = ttk.Scrollbar(active_frame)
        active_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.twitter_user_active_listbox = tk.Listbox(active_frame, yscrollcommand=active_scroll.set, height=12,
                                                      bg='#e8f5e9', selectmode=tk.EXTENDED)
        self.twitter_user_active_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        active_scroll.config(command=self.twitter_user_active_listbox.yview)

        # Middle buttons
        middle_frame = ttk.Frame(lists_frame)
        middle_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(middle_frame, text="").pack()  # Spacer
        ttk.Button(middle_frame, text="→", width=3, command=lambda: self.move_twitter_user_to_inactive()).pack(pady=2)
        ttk.Button(middle_frame, text="←", width=3, command=lambda: self.move_twitter_user_to_active()).pack(pady=2)

        # Inactive list
        inactive_frame = ttk.Frame(lists_frame)
        inactive_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(5, 0))
        ttk.Label(inactive_frame, text="Inactive (Skipped)", font=('TkDefaultFont', 9, 'bold')).pack()
        inactive_scroll = ttk.Scrollbar(inactive_frame)
        inactive_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.twitter_user_inactive_listbox = tk.Listbox(inactive_frame, yscrollcommand=inactive_scroll.set, height=12,
                                                        bg='#ffebee', selectmode=tk.EXTENDED)
        self.twitter_user_inactive_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        inactive_scroll.config(command=self.twitter_user_inactive_listbox.yview)

        # Buttons
        btn_frame = ttk.Frame(user_frame)
        btn_frame.pack(fill='x', pady=5)
        self.twitter_user_entry = ttk.Entry(btn_frame)
        self.twitter_user_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        ttk.Button(btn_frame, text="Add", command=self.add_twitter_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self.remove_twitter_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Scrape Active", command=self.scrape_all_twitter_users).pack(side=tk.LEFT, padx=2)
        
        # Tweet limit control
        limit_frame = ttk.Frame(user_frame)
        limit_frame.pack(fill='x', pady=5)
        ttk.Label(limit_frame, text="Tweets to scan per user:").pack(side=tk.LEFT, padx=(0, 5))
        self.twitter_limit_var = tk.IntVar(value=500)
        ttk.Spinbox(limit_frame, from_=50, to=5000, increment=50, textvariable=self.twitter_limit_var, width=10).pack(side=tk.LEFT)
        ttk.Label(limit_frame, text="(Higher = more files, slower)", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(5, 0))
        
        self.twitter_unlimited_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(limit_frame, text="⚡ Scrape ALL tweets (unlimited)", variable=self.twitter_unlimited_var).pack(side=tk.LEFT, padx=(15, 0))

        # Load existing data
        self.refresh_twitter_user_lists()
    
    def create_website_tab(self):
        """Create website scraping tab with Active/Inactive lists"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Websites")
        
        # Websites section
        website_frame = ttk.LabelFrame(tab, text="Websites & Sitemaps", padding=10)
        website_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        info_label = ttk.Label(website_frame, 
                              text="Add website URLs or sitemap.xml URLs to scrape media from",
                              foreground="gray")
        info_label.pack(anchor='w', pady=(0, 5))
        
        format_label = ttk.Label(website_frame,
                                text="Format: URL or URL FolderName (e.g., https://example.com/user/john John)",
                                foreground="blue", font=('TkDefaultFont', 8))
        format_label.pack(anchor='w', pady=(0, 5))
        
        # Dual listbox layout (Active | Inactive)
        lists_frame = ttk.Frame(website_frame)
        lists_frame.pack(fill='both', expand=True)
        
        # Active list
        active_frame = ttk.Frame(lists_frame)
        active_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        ttk.Label(active_frame, text="Active (Will be scraped)", font=('TkDefaultFont', 9, 'bold')).pack()
        active_scroll = ttk.Scrollbar(active_frame)
        active_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.website_active_listbox = tk.Listbox(active_frame, yscrollcommand=active_scroll.set, height=10,
                                                   bg='#e8f5e9', selectmode=tk.EXTENDED)
        self.website_active_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        active_scroll.config(command=self.website_active_listbox.yview)
        
        # Middle buttons
        middle_frame = ttk.Frame(lists_frame)
        middle_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(middle_frame, text="").pack()  # Spacer
        ttk.Button(middle_frame, text="→", width=3, command=lambda: self.move_website_to_inactive()).pack(pady=2)
        ttk.Button(middle_frame, text="←", width=3, command=lambda: self.move_website_to_active()).pack(pady=2)
        
        # Inactive list
        inactive_frame = ttk.Frame(lists_frame)
        inactive_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(5, 0))
        
        ttk.Label(inactive_frame, text="Inactive (Skipped)", font=('TkDefaultFont', 9, 'bold')).pack()
        inactive_scroll = ttk.Scrollbar(inactive_frame)
        inactive_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.website_inactive_listbox = tk.Listbox(inactive_frame, yscrollcommand=inactive_scroll.set, height=10,
                                                     bg='#ffebee', selectmode=tk.EXTENDED)
        self.website_inactive_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        inactive_scroll.config(command=self.website_inactive_listbox.yview)
        
        # Pagination and scroll settings
        pagination_frame = ttk.Frame(website_frame)
        pagination_frame.pack(fill='x', pady=5)
        
        ttk.Label(pagination_frame, text="Max pages:").pack(side=tk.LEFT, padx=(0, 5))
        self.website_max_pages = ttk.Entry(pagination_frame, width=5)
        self.website_max_pages.pack(side=tk.LEFT, padx=2)
        self.website_max_pages.insert(0, "50")
        ttk.Label(pagination_frame, text="(For sitemaps: URLs to process)  ", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(pagination_frame, text="Scroll count:").pack(side=tk.LEFT, padx=(10, 5))
        self.website_scroll_count = ttk.Entry(pagination_frame, width=5)
        self.website_scroll_count.pack(side=tk.LEFT, padx=2)
        self.website_scroll_count.insert(0, "20")
        ttk.Label(pagination_frame, text="(infinite scroll, higher = more content)", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(pagination_frame, text="Workers:").pack(side=tk.LEFT, padx=(10, 5))
        self.website_workers = ttk.Entry(pagination_frame, width=5)
        self.website_workers.pack(side=tk.LEFT, padx=2)
        self.website_workers.insert(0, "5")
        ttk.Label(pagination_frame, text="(concurrent downloads, 3-10 recommended)", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

        # Aggressive popup removal toggle
        self.website_aggressive_popup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(pagination_frame,
                text="Aggressive popup removal",
                variable=self.website_aggressive_popup_var).pack(side=tk.LEFT, padx=(15,5))
        ttk.Label(pagination_frame, text="(disable if a site needs its modal)", foreground="gray", font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
        
        # Buttons
        btn_frame = ttk.Frame(website_frame)
        btn_frame.pack(fill='x', pady=5)
        
        self.website_entry = ttk.Entry(btn_frame)
        self.website_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        
        ttk.Button(btn_frame, text="Add", command=self.add_website).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Remove", command=self.remove_website).pack(side=tk.LEFT, padx=2)
        
        # Second button row for scan and download
        btn_frame2 = ttk.Frame(website_frame)
        btn_frame2.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame2, text="Scan Selected", command=self.scan_selected_website).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame2, text="🚀 Scrape & Download All", command=self.scrape_all_websites).pack(side=tk.LEFT, padx=2)
        
        # Load existing data
        self.refresh_website_lists()
    
    def create_onlyfans_tab(self):
        """Create OnlyFans tab with OF-DL launcher"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="OnlyFans")
        
        # Center container
        container = ttk.Frame(tab)
        container.pack(fill='both', expand=True)
        
        # Center frame
        center_frame = ttk.Frame(container)
        center_frame.place(relx=0.5, rely=0.5, anchor='center')
        
        # Info section
        info_frame = ttk.LabelFrame(center_frame, text="OnlyFans Content Downloader (OF-DL)", padding=20)
        info_frame.pack(padx=20, pady=20)
        
        ttk.Label(info_frame, text="Uses OF-DL tool to download posts, messages, and media from OnlyFans creators.",
                 foreground="gray", font=('TkDefaultFont', 9)).pack(anchor='w', pady=(0, 5))
        
        # Disclaimer
        disclaimer_frame = ttk.Frame(info_frame)
        disclaimer_frame.pack(fill='x', pady=(5, 10))
        ttk.Label(disclaimer_frame, text="⚠️ DISCLAIMER:", foreground="red", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w')
        disclaimer_text = "OF-DL is a third-party tool (not created by us). It may stop working if OnlyFans changes their API or security. For direct API access, see instructions below."
        ttk.Label(disclaimer_frame, text=disclaimer_text, foreground="#d35400", font=('TkDefaultFont', 8), wraplength=500, justify='left').pack(anchor='w', pady=(2, 5))
        
        # API alternative button
        ttk.Button(disclaimer_frame, text="📋 Show OnlyFans API Instructions", command=self._show_onlyfans_api_help).pack(anchor='w', pady=(5, 0))
        
        # OF-DL path configuration
        ofdl_path_frame = ttk.Frame(info_frame)
        ofdl_path_frame.pack(fill='x', pady=(0, 15))
        ttk.Label(ofdl_path_frame, text="OF-DL.exe Path:").pack(side=tk.LEFT)
        self.ofdl_exe_path = ttk.Entry(ofdl_path_frame, width=50)
        self.ofdl_exe_path.pack(side=tk.LEFT, padx=5, fill='x', expand=True)
        self.ofdl_exe_path.insert(0, str(self.config.get('onlyfans.ofdl_path', '')))
        ttk.Button(ofdl_path_frame, text="Browse", command=self.browse_ofdl_exe).pack(side=tk.LEFT, padx=2)
        ttk.Button(ofdl_path_frame, text="Download OF-DL", command=self.open_ofdl_download).pack(side=tk.LEFT, padx=2)
        
        # Launch button
        launch_frame = ttk.Frame(info_frame)
        launch_frame.pack(pady=10)
        ttk.Button(launch_frame, text="🚀 Open OF-DL", command=self.launch_ofdl_exe, 
                  width=30, style='Accent.TButton').pack()
        
        ttk.Label(info_frame, text="OF-DL handles authentication automatically using its built-in browser.",
                 foreground="green", font=('TkDefaultFont', 8)).pack(anchor='w', pady=(10, 0))
    
    def create_duplicates_tab(self):
        """Create duplicates management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Duplicates")
        # Make the entire tab scrollable
        container = tk.Frame(tab, highlightthickness=2, highlightbackground='#2c3e50', relief='solid')
        container.pack(fill='both', expand=True, padx=10, pady=10)
        canvas = tk.Canvas(container, bd=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=vscroll.set)
        # Enable mouse wheel scrolling (Windows/Linux compatible basics)
        def _on_mousewheel(event):
            try:
                delta = int(-1 * (event.delta / 120))
            except Exception:
                delta = -1
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        canvas.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')

        # Info section
        info_frame = ttk.LabelFrame(scrollable, text="Duplicate Detection System", padding=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        # store for maximize/restore
        self.dup_info_frame = info_frame
        
        info_text = "SHA256 file hashing guarantees 100% duplicate detection even if files are moved or renamed.\n" \
                   "Scan your downloads or any drive/folder, review duplicates, and choose to delete or relocate them."
        ttk.Label(info_frame, text=info_text, foreground="gray", wraplength=800).pack(anchor='w')
        
        # Scan controls removed (Quick Run by Drive replaces these options)

        # Quick drive selection runner
        quick_frame = ttk.LabelFrame(scrollable, text="Quick Run by Drive", padding=10)
        quick_frame.pack(fill='x', padx=10, pady=5)
        self.dup_quick_frame = quick_frame

        row = ttk.Frame(quick_frame)
        row.pack(fill='x', pady=2)
        ttk.Label(row, text="Drive:").pack(side=tk.LEFT, padx=(0,4))
        self.drive_select_var = tk.StringVar()
        self.drive_select_combo = ttk.Combobox(row, textvariable=self.drive_select_var, width=8, state='readonly')
        self.drive_select_combo.pack(side=tk.LEFT)
        ttk.Button(row, text="Refresh", command=self.refresh_drive_list, width=10).pack(side=tk.LEFT, padx=6)
        
        # Folder path option
        row_folder = ttk.Frame(quick_frame)
        row_folder.pack(fill='x', pady=2)
        ttk.Label(row_folder, text="Or scan specific folder:").pack(side=tk.LEFT, padx=(0,4))
        self.dup_folder_var = tk.StringVar(value="")
        ttk.Entry(row_folder, textvariable=self.dup_folder_var, width=60).pack(side=tk.LEFT)
        ttk.Button(row_folder, text="Browse...", command=self.browse_dup_folder, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Button(row_folder, text="Run Folder", command=self.run_folder_duplicates, width=15).pack(side=tk.LEFT, padx=6)
        
        # Global sweep button
        row_global = ttk.Frame(quick_frame)
        row_global.pack(fill='x', pady=6)
        ttk.Label(row_global, text="⚡ Quick action:", font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT, padx=(0,4))
        ttk.Button(row_global, text="Global Sweep (All Downloads)", command=self.run_global_sweep, width=30).pack(side=tk.LEFT, padx=6)
        ttk.Label(row_global, text="← Scans entire Downloads folder for duplicates", foreground="gray").pack(side=tk.LEFT)
        
        row_dest = ttk.Frame(quick_frame)
        row_dest.pack(fill='x', pady=2)
        ttk.Label(row_dest, text="Destination folder name:").pack(side=tk.LEFT, padx=(0,4))
        self.drive_dest_var = tk.StringVar(value="duplicates")
        ttk.Entry(row_dest, textvariable=self.drive_dest_var, width=24).pack(side=tk.LEFT)
        # Simple include-media toggle controlling filter presets
        self.include_media_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Include media (images/videos/audio)", variable=self.include_media_var,
                command=self._on_include_media_toggle).pack(side=tk.LEFT, padx=(8,4))
        ttk.Button(row, text="Run Selected Drive", command=self.run_selected_drive_preserve_duplicates, width=22).pack(side=tk.LEFT, padx=8)

        # Initialize drive list
        self.refresh_drive_list()

        # Filters
        filters_frame = ttk.LabelFrame(scrollable, text="Filters", padding=10)
        filters_frame.pack(fill='x', padx=10, pady=5)
        self.dup_filters_frame = filters_frame

        # Row 1: Type groups
        row1 = ttk.Frame(filters_frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text="Include types:").pack(side=tk.LEFT, padx=(0, 6))
        self.filter_images = tk.BooleanVar(value=True)
        self.filter_videos = tk.BooleanVar(value=True)
        self.filter_audio = tk.BooleanVar(value=False)
        self.filter_docs = tk.BooleanVar(value=False)
        self.filter_archives = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Images", variable=self.filter_images).pack(side=tk.LEFT)
        ttk.Checkbutton(row1, text="Videos", variable=self.filter_videos).pack(side=tk.LEFT)
        ttk.Checkbutton(row1, text="Audio", variable=self.filter_audio).pack(side=tk.LEFT)
        ttk.Checkbutton(row1, text="Docs", variable=self.filter_docs).pack(side=tk.LEFT)
        ttk.Checkbutton(row1, text="Archives", variable=self.filter_archives).pack(side=tk.LEFT)

        # Row 2: Custom extensions and min size
        row2 = ttk.Frame(filters_frame)
        row2.pack(fill='x', pady=2)
        ttk.Label(row2, text="Custom extensions (comma-separated):").pack(side=tk.LEFT)
        self.filter_custom_exts = tk.StringVar(value="")
        ttk.Entry(row2, textvariable=self.filter_custom_exts, width=40).pack(side=tk.LEFT, padx=6)
        ttk.Label(row2, text="Min size (MB):").pack(side=tk.LEFT, padx=(10,4))
        self.filter_min_size_mb = tk.StringVar(value="0")
        ttk.Entry(row2, textvariable=self.filter_min_size_mb, width=8).pack(side=tk.LEFT)

        # Row 3: Exclusions and attributes
        row3 = ttk.Frame(filters_frame)
        row3.pack(fill='x', pady=2)
        ttk.Label(row3, text="Exclude paths (semicolon-separated):").pack(side=tk.LEFT)
        self.filter_exclude_paths = tk.StringVar(value="Windows;Program Files;Program Files (x86);ProgramData;$Recycle.Bin;System Volume Information")
        ttk.Entry(row3, textvariable=self.filter_exclude_paths, width=70).pack(side=tk.LEFT, padx=6)
        self.filter_ignore_hidden_system = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Ignore hidden/system files", variable=self.filter_ignore_hidden_system).pack(side=tk.LEFT, padx=(10,0))
        
        # Find & manage duplicates
        manage_frame = ttk.LabelFrame(scrollable, text="Manage Duplicates", padding=10)
        manage_frame.pack(fill='x', padx=10, pady=5)
        self.dup_manage_frame = manage_frame
        
        ttk.Label(manage_frame, text="After scanning, manage found duplicates:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        
        btn_row4 = ttk.Frame(manage_frame)
        btn_row4.pack(fill='x', pady=2)
        ttk.Button(btn_row4, text="Delete All Duplicates (Auto)", command=self.delete_all_duplicates, width=25).pack(side=tk.LEFT, padx=2)
        ttk.Label(btn_row4, text="Automatically delete all duplicates, keeping one from each group", foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # Statistics
        stats_frame = ttk.LabelFrame(scrollable, text="Statistics & Info", padding=10)
        stats_frame.pack(fill='x', padx=10, pady=5)
        self.dup_stats_frame = stats_frame
        
        btn_row5 = ttk.Frame(stats_frame)
        btn_row5.pack(fill='x', pady=2)
        ttk.Button(btn_row5, text="View Statistics", command=self.show_duplicate_stats, width=25).pack(side=tk.LEFT, padx=2)
        ttk.Label(btn_row5, text="Show file counts, sizes, and database stats", foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # Activity log
        # Progress section (duplicates-specific)
        prog_frame = ttk.LabelFrame(scrollable, text="Run Progress", padding=10)
        prog_frame.pack(fill='x', padx=10, pady=5)
        self.dup_prog_frame = prog_frame
        self.dup_progress_var = tk.StringVar(value="Idle")
        ttk.Label(prog_frame, textvariable=self.dup_progress_var).pack(anchor='w')
        self.dup_progress_bar = ttk.Progressbar(prog_frame, mode='determinate')
        self.dup_progress_bar.pack(fill='x', pady=(6,0))
        self.dup_progress_bar.pack_forget()

        log_frame = ttk.LabelFrame(scrollable, text="Activity Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        self.dup_log_frame = log_frame
        log_header = ttk.Frame(log_frame)
        log_header.pack(fill='x')
        ttk.Button(log_header, text="Pop‑out Log", command=self.open_floating_log, width=14).pack(side=tk.LEFT)
        ttk.Button(log_header, text="Maximize", command=self.toggle_dup_log_maximize, width=12).pack(side=tk.LEFT, padx=6)
        ttk.Label(log_header, text="Opens a large, resizable window that mirrors this log", foreground="gray").pack(side=tk.LEFT, padx=8)

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill='both', expand=True, pady=(6,0))
        self.dup_log_text = tk.Text(log_container, height=16, wrap='word')
        dup_log_scroll = ttk.Scrollbar(log_container, orient='vertical', command=self.dup_log_text.yview)
        self.dup_log_text.configure(yscrollcommand=dup_log_scroll.set)
        self.dup_log_text.pack(side=tk.LEFT, fill='both', expand=True)
        dup_log_scroll.pack(side=tk.RIGHT, fill='y')
    
    def create_settings_tab(self):
        """Create settings configuration tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Settings")
        
        # Create PanedWindow to split settings and log
        paned = ttk.PanedWindow(tab, orient=tk.VERTICAL)
        paned.pack(fill='both', expand=True)
        
        # Top pane: scrollable settings
        settings_container = ttk.Frame(paned)
        paned.add(settings_container, weight=3)
        
        # Create a LabelFrame for the settings with border
        settings_frame = ttk.LabelFrame(settings_container, text="Configuration Settings", padding=10, relief='solid', borderwidth=2)
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create canvas and scrollbar inside the frame
        canvas = tk.Canvas(settings_frame, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mouse wheel to canvas when mouse enters
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # Reddit settings (no API key required - uses gallery-dl)
        reddit_header = ttk.Frame(scrollable_frame)
        reddit_header.pack(fill='x', padx=10, pady=(5,0))
        
        reddit_frame = ttk.LabelFrame(reddit_header, text="Reddit Settings", padding=10, relief='solid', borderwidth=1)
        reddit_frame.pack(side=tk.LEFT, fill='both', expand=True)
        
        reddit_help_btn = ttk.Button(reddit_header, text="?", width=3, command=self._show_reddit_api_help)
        reddit_help_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(reddit_frame, text="ℹ️ Reddit scraping uses gallery-dl (no API key needed)", 
                 foreground='#27ae60', font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=5)
        ttk.Label(reddit_frame, text="gallery-dl will be automatically used for downloading Reddit content.", 
                 wraplength=500).pack(anchor='w', pady=2)
        
        reddit_frame.columnconfigure(0, weight=1)
        
        # Twitter settings
        twitter_header = ttk.Frame(scrollable_frame)
        twitter_header.pack(fill='x', padx=10, pady=(5,0))
        
        twitter_frame = ttk.LabelFrame(twitter_header, text="Twitter API Settings", padding=10, relief='solid', borderwidth=1)
        twitter_frame.pack(side=tk.LEFT, fill='both', expand=True)
        
        twitter_help_btn = ttk.Button(twitter_header, text="?", width=3, command=self._show_twitter_api_help)
        twitter_help_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(twitter_frame, text="Bearer Token:").grid(row=0, column=0, sticky='w', pady=2)
        self.twitter_bearer = ttk.Entry(twitter_frame, width=50, show='*')
        self.twitter_bearer.grid(row=0, column=1, sticky='ew', pady=2, padx=5)
        self.twitter_bearer.insert(0, str(self.config.get('twitter.bearer_token', '')))
        
        ttk.Label(twitter_frame, text="API Key:").grid(row=1, column=0, sticky='w', pady=2)
        self.twitter_api_key = ttk.Entry(twitter_frame, width=50)
        self.twitter_api_key.grid(row=1, column=1, sticky='ew', pady=2, padx=5)
        self.twitter_api_key.insert(0, str(self.config.get('twitter.api_key', '')))
        
        ttk.Label(twitter_frame, text="API Secret:").grid(row=2, column=0, sticky='w', pady=2)
        self.twitter_api_secret = ttk.Entry(twitter_frame, width=50, show='*')
        self.twitter_api_secret.grid(row=2, column=1, sticky='ew', pady=2, padx=5)
        self.twitter_api_secret.insert(0, str(self.config.get('twitter.api_secret', '')))
        
        ttk.Label(twitter_frame, text="Access Token:").grid(row=3, column=0, sticky='w', pady=2)
        self.twitter_access_token = ttk.Entry(twitter_frame, width=50, show='*')
        self.twitter_access_token.grid(row=3, column=1, sticky='ew', pady=2, padx=5)
        self.twitter_access_token.insert(0, str(self.config.get('twitter.access_token', '')))
        
        ttk.Label(twitter_frame, text="Access Token Secret:").grid(row=4, column=0, sticky='w', pady=2)
        self.twitter_access_secret = ttk.Entry(twitter_frame, width=50, show='*')
        self.twitter_access_secret.grid(row=4, column=1, sticky='ew', pady=2, padx=5)
        self.twitter_access_secret.insert(0, str(self.config.get('twitter.access_token_secret', '')))
        
        twitter_frame.columnconfigure(1, weight=1)
        
        # OnlyFans Download Options (Authentication handled by OF-DL)
        onlyfans_options_frame = ttk.LabelFrame(scrollable_frame, text="OnlyFans Download Options", padding=10, relief='solid', borderwidth=1)
        onlyfans_options_frame.pack(fill='x', padx=10, pady=5)
        
        # Content Type Options (Column 1)
        content_col = ttk.Frame(onlyfans_options_frame)
        content_col.grid(row=0, column=0, sticky='nw', padx=5)
        ttk.Label(content_col, text="📥 Content Types:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0,4))
        
        self.of_download_posts = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_posts', True)))
        ttk.Checkbutton(content_col, text="Download Posts (free)", variable=self.of_download_posts).pack(anchor='w', pady=1)
        
        self.of_download_paid_posts = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_paid_posts', True)))
        ttk.Checkbutton(content_col, text="Download Paid Posts", variable=self.of_download_paid_posts).pack(anchor='w', pady=1)
        
        self.of_download_messages = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_messages', True)))
        ttk.Checkbutton(content_col, text="Download Messages (free)", variable=self.of_download_messages).pack(anchor='w', pady=1)
        
        self.of_download_paid_messages = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_paid_messages', True)))
        ttk.Checkbutton(content_col, text="Download Paid Messages", variable=self.of_download_paid_messages).pack(anchor='w', pady=1)
        
        self.of_download_stories = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_stories', True)))
        ttk.Checkbutton(content_col, text="Download Stories", variable=self.of_download_stories).pack(anchor='w', pady=1)
        
        self.of_download_highlights = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_highlights', True)))
        ttk.Checkbutton(content_col, text="Download Highlights", variable=self.of_download_highlights).pack(anchor='w', pady=1)
        
        self.of_download_archived = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_archived', True)))
        ttk.Checkbutton(content_col, text="Download Archived Posts", variable=self.of_download_archived).pack(anchor='w', pady=1)
        
        self.of_download_streams = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_streams', True)))
        ttk.Checkbutton(content_col, text="Download Streams", variable=self.of_download_streams).pack(anchor='w', pady=1)
        
        # Media Type Options (Column 2)
        media_col = ttk.Frame(onlyfans_options_frame)
        media_col.grid(row=0, column=1, sticky='nw', padx=5)
        ttk.Label(media_col, text="🎬 Media Types:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0,4))
        
        self.of_download_images = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_images', True)))
        ttk.Checkbutton(media_col, text="Download Images", variable=self.of_download_images).pack(anchor='w', pady=1)
        
        self.of_download_videos = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_videos', True)))
        ttk.Checkbutton(media_col, text="Download Videos", variable=self.of_download_videos).pack(anchor='w', pady=1)
        
        self.of_download_audios = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_audios', True)))
        ttk.Checkbutton(media_col, text="Download Audios", variable=self.of_download_audios).pack(anchor='w', pady=1)
        
        self.of_download_avatar_header = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_avatar_header', True)))
        ttk.Checkbutton(media_col, text="Download Avatar/Header", variable=self.of_download_avatar_header).pack(anchor='w', pady=1)
        
        # Organization Options (Column 3)
        org_col = ttk.Frame(onlyfans_options_frame)
        org_col.grid(row=0, column=2, sticky='nw', padx=5)
        ttk.Label(org_col, text="📁 Organization:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0,4))
        
        self.of_folder_per_post = tk.BooleanVar(value=bool(self.config.get('onlyfans.folder_per_post', False)))
        ttk.Checkbutton(org_col, text="Folder per Post", variable=self.of_folder_per_post).pack(anchor='w', pady=1)
        
        self.of_folder_per_paid_post = tk.BooleanVar(value=bool(self.config.get('onlyfans.folder_per_paid_post', False)))
        ttk.Checkbutton(org_col, text="Folder per Paid Post", variable=self.of_folder_per_paid_post).pack(anchor='w', pady=1)
        
        self.of_folder_per_message = tk.BooleanVar(value=bool(self.config.get('onlyfans.folder_per_message', False)))
        ttk.Checkbutton(org_col, text="Folder per Message", variable=self.of_folder_per_message).pack(anchor='w', pady=1)
        
        self.of_folder_per_paid_message = tk.BooleanVar(value=bool(self.config.get('onlyfans.folder_per_paid_message', False)))
        ttk.Checkbutton(org_col, text="Folder per Paid Message", variable=self.of_folder_per_paid_message).pack(anchor='w', pady=1)
        
        # Advanced Options (Column 4)
        advanced_col = ttk.Frame(onlyfans_options_frame)
        advanced_col.grid(row=0, column=3, sticky='nw', padx=5)
        ttk.Label(advanced_col, text="⚙️ Advanced:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(0,4))
        
        self.of_skip_ads = tk.BooleanVar(value=bool(self.config.get('onlyfans.skip_ads', False)))
        ttk.Checkbutton(advanced_col, text="Skip Ads (#ad posts)", variable=self.of_skip_ads).pack(anchor='w', pady=1)
        
        self.of_ignore_own_messages = tk.BooleanVar(value=bool(self.config.get('onlyfans.ignore_own_messages', False)))
        ttk.Checkbutton(advanced_col, text="Ignore Own Messages", variable=self.of_ignore_own_messages).pack(anchor='w', pady=1)
        
        self.of_include_expired = tk.BooleanVar(value=bool(self.config.get('onlyfans.include_expired', False)))
        ttk.Checkbutton(advanced_col, text="Include Expired Subs", variable=self.of_include_expired).pack(anchor='w', pady=1)
        
        self.of_include_restricted = tk.BooleanVar(value=bool(self.config.get('onlyfans.include_restricted', False)))
        ttk.Checkbutton(advanced_col, text="Include Restricted", variable=self.of_include_restricted).pack(anchor='w', pady=1)
        
        self.of_download_duplicates = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_duplicates', False)))
        ttk.Checkbutton(advanced_col, text="Download Duplicates", variable=self.of_download_duplicates).pack(anchor='w', pady=1)
        
        self.of_download_incrementally = tk.BooleanVar(value=bool(self.config.get('onlyfans.download_incrementally', False)))
        ttk.Checkbutton(advanced_col, text="Incremental Downloads", variable=self.of_download_incrementally).pack(anchor='w', pady=1)
        
        # Download settings
        download_frame = ttk.LabelFrame(scrollable_frame, text="Download Settings", padding=10, relief='solid', borderwidth=1)
        download_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(download_frame, text="Download Path:").grid(row=0, column=0, sticky='w', pady=2)
        self.download_path = ttk.Entry(download_frame, width=40)
        self.download_path.grid(row=0, column=1, sticky='ew', pady=2, padx=5)
        self.download_path.insert(0, str(self.config.get('downloads.base_path', 'Downloads')))
        
        ttk.Button(download_frame, text="Browse", command=self.browse_download_path).grid(row=0, column=2, padx=5)

        # Auto-organize at startup toggle
        self.auto_organize_startup = tk.BooleanVar(value=bool(self.config.get('downloads.auto_organize_startup', False)))
        def _toggle_auto_org():
            try:
                self.config.set('downloads.auto_organize_startup', bool(self.auto_organize_startup.get()))
                self.log(f"Auto-organize on startup: {bool(self.auto_organize_startup.get())}")
            except Exception as e:
                self.log(f"Failed to update setting: {e}")
        ttk.Checkbutton(download_frame, text="Auto-organize downloads on startup",
                        variable=self.auto_organize_startup, command=_toggle_auto_org).grid(row=1, column=0, columnspan=3, sticky='w', pady=(6,0))
        
        download_frame.columnconfigure(1, weight=1)
        
        # History management
        history_frame = ttk.LabelFrame(scrollable_frame, text="Download History", padding=10, relief='solid', borderwidth=1)
        history_frame.pack(fill='x', padx=10, pady=5)
        
        history_info = ttk.Label(history_frame, text="Track downloaded content to avoid re-downloading", foreground="gray")
        history_info.pack(anchor='w', pady=(0, 5))
        
        # Option to re-download deleted files
        self.redownload_deleted = tk.BooleanVar(value=bool(self.config.get('downloads.redownload_deleted_files', True)))
        ttk.Checkbutton(history_frame, text="Re-download if file was manually deleted", 
                       variable=self.redownload_deleted).pack(anchor='w', pady=(0, 5))
        
        history_btn_frame = ttk.Frame(history_frame)
        history_btn_frame.pack(fill='x')
        
        ttk.Button(history_btn_frame, text="View Statistics", command=self.show_history_stats).pack(side=tk.LEFT, padx=2)
        ttk.Button(history_btn_frame, text="Clear All History", command=self.clear_all_history).pack(side=tk.LEFT, padx=2)
        
        # Log and organization buttons
        logscan_frame = ttk.LabelFrame(scrollable_frame, text="Diagnostics & Log Export", padding=10, relief='solid', borderwidth=1)
        logscan_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(logscan_frame, text="Save Activity Log", command=self.save_activity_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(logscan_frame, text="Organize Downloads (videos/images/gifs)", command=self.organize_downloads).pack(side=tk.LEFT, padx=5)
        
        # Save button
        ttk.Button(scrollable_frame, text="Save Settings", command=self.save_settings).pack(pady=10)
        
        # Pack canvas and scrollbar using grid for better control
        canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Configure grid weights
        settings_frame.grid_rowconfigure(0, weight=1)
        settings_frame.grid_columnconfigure(0, weight=1)
        
        # Bottom pane: Activity Log (always visible)
        log_container = ttk.Frame(paned)
        paned.add(log_container, weight=1)
        
        log_frame = ttk.LabelFrame(log_container, text="Activity Log", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)
    
    def _auto_organize_startup(self):
        """Run organize downloads at startup if setting enabled."""
        try:
            if bool(self.config.get('downloads.auto_organize_startup', False)):
                self.log("Auto-organize on startup enabled — organizing downloads...")
                self.organize_downloads()
        except Exception as e:
            self.log(f"Auto-organize failed: {e}")
    
    def _load_website_scrape_state(self):
        """Load website scraping state from file"""
        if os.path.exists(self.website_scrape_state_file):
            try:
                with open(self.website_scrape_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'completed_websites': [], 'current_website': None}
        return {'completed_websites': [], 'current_website': None}
    
    def _save_website_scrape_state(self):
        """Save website scraping state to file"""
        try:
            with open(self.website_scrape_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.website_scrape_state, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Failed to save scrape state: {e}")
    
    def _clear_website_scrape_state(self):
        """Clear website scraping state for fresh start"""
        self.website_scrape_state = {'completed_websites': [], 'current_website': None}
        self._save_website_scrape_state()
        self.log("Cleared website scraping state")
    
    def _create_menu_bar(self):
        """Create menu bar with File, Tools, View, and Help menus"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Activity Log", command=self.save_activity_log, accelerator="Ctrl+S")
        file_menu.add_command(label="Clear Activity Log", command=lambda: self.log_text.delete('1.0', tk.END))
        file_menu.add_separator()
        file_menu.add_command(label="Open Downloads Folder", command=self._open_downloads_folder)
        file_menu.add_command(label="Open Config Folder", command=lambda: os.startfile(self.botfiles_dir))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Alt+F4")
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Scan Download Folders", command=self.scan_download_folders)
        tools_menu.add_command(label="Organize Downloads", command=self.organize_downloads)
        tools_menu.add_command(label="Flatten Folder Structure", command=self.flatten_folder_structure)
        tools_menu.add_command(label="Delete Empty Folders", command=self.delete_empty_folders)
        tools_menu.add_separator()
        tools_menu.add_command(label="View Statistics", command=self.show_statistics)
        tools_menu.add_command(label="Clear Download History", command=self._clear_history_with_confirm)
        tools_menu.add_command(label="Clear Scrape History", command=self._clear_scrape_history_with_confirm)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Theme (Light/Dark)", command=self._toggle_theme, accelerator="Ctrl+T")
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Show Status Bar", variable=tk.BooleanVar(value=True))
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        help_menu.add_command(label="About", command=self._show_about)
    
    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-s>', lambda e: self.save_activity_log())
        self.root.bind('<Control-t>', lambda e: self._toggle_theme())
        self.root.bind('<Control-o>', lambda e: self._open_downloads_folder())
        self.root.bind('<F5>', lambda e: self._refresh_current_tab())
    
    def _apply_theme(self):
        """Apply current theme to the GUI"""
        if self.current_theme == 'dark':
            # Dark theme colors
            bg_color = '#2b2b2b'
            fg_color = '#ffffff'
            select_bg = '#404040'
            self.style.theme_use('clam')
            self.style.configure('TFrame', background=bg_color)
            self.style.configure('TLabel', background=bg_color, foreground=fg_color)
            self.style.configure('TLabelframe', background=bg_color, foreground=fg_color)
            self.style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color)
            self.style.configure('TButton', background='#404040', foreground=fg_color)
            self.style.configure('TCheckbutton', background=bg_color, foreground=fg_color)
            self.style.configure('TRadiobutton', background=bg_color, foreground=fg_color)
            self.root.configure(bg=bg_color)
        else:
            # Light theme (default)
            self.style.theme_use('vista' if os.name == 'nt' else 'clam')
    
    def _toggle_theme(self):
        """Toggle between light and dark theme"""
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self._apply_theme()
        self.log(f"Switched to {self.current_theme} theme")
    
    def _open_downloads_folder(self):
        """Open downloads folder in file explorer"""
        download_path = str(self.config.get('downloads.base_path', 'Downloads'))
        if os.path.exists(download_path):
            os.startfile(download_path)
        else:
            messagebox.showwarning("Folder Not Found", f"Download folder does not exist:\n{download_path}")
    
    def _refresh_current_tab(self):
        """Refresh the current active tab"""
        current_tab = self.notebook.index(self.notebook.select())
        tab_name = self.notebook.tab(current_tab, "text")
        self.log(f"Refreshing {tab_name} tab...")
        
        if "Reddit" in tab_name:
            self.refresh_subreddit_lists()
            self.refresh_reddit_user_lists()
        elif "Twitter" in tab_name:
            self.refresh_twitter_user_lists()
    
    def _clear_history_with_confirm(self):
        """Clear download history with confirmation"""
        result = messagebox.askyesno("Clear History", 
            "Are you sure you want to clear all download history?\n\n" +
            "This will allow re-downloading previously downloaded files.")
        if result:
            self.download_history.clear_all_history()
            self.log("✓ Download history cleared")
    
    def _clear_scrape_history_with_confirm(self):
        """Clear all scrape history including website state and download queue"""
        result = messagebox.askyesno("Clear Scrape History",
            "This will clear:\n" +
            "• Website scrape state (completed websites)\n" +
            "• Download queue (pending downloads)\n" +
            "• Download history (allows re-downloading)\n\n" +
            "Are you sure you want to start completely fresh?")
        if result:
            # Clear website scrape state
            self._clear_website_scrape_state()
            
            # Clear download queue
            queue_path = os.path.join(self.botfiles_dir, 'download_queue.json')
            if os.path.exists(queue_path):
                try:
                    with open(queue_path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    self.log("✓ Download queue cleared")
                except Exception as e:
                    self.log(f"Error clearing download queue: {e}")
            
            # Clear download history
            self.download_history.clear_all_history()
            
            self.log("✅ All scrape history cleared - starting fresh!")
    
    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts = """Keyboard Shortcuts:
        
Ctrl+S      Save Activity Log
Ctrl+T      Toggle Theme (Light/Dark)
Ctrl+O      Open Downloads Folder
F5          Refresh Current Tab
Alt+F4      Exit Application

Navigation:
Ctrl+Tab    Switch Tabs
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)
    
    def _show_reddit_api_help(self):
        """Show instructions for using gallery-dl with Reddit"""
        # Create a custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Reddit Help")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Content
        content = ttk.Frame(scrollable_frame, padding=10)
        content.pack(fill='both', expand=True)
        
        ttk.Label(content, text="📝 Reddit Scraping with gallery-dl", 
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        ttk.Label(content, text="✅ No API Key Required!", 
                 font=('TkDefaultFont', 10, 'bold'), foreground='#27ae60').pack(anchor='w', pady=(5, 10))
        
        # Instructions
        instructions = """This scraper uses gallery-dl to download Reddit content.
No Reddit API credentials are needed!

How to use:

1. Enter a subreddit name (e.g., "pics", "wallpapers")
   OR a Reddit username

2. Click "Scrape" to download media

3. gallery-dl will automatically download:
   • Images from posts
   • Videos from posts
   • Gallery albums
   • Crossposts

Note: gallery-dl scrapes public Reddit content without authentication.
For private or age-restricted content, you may need to configure
browser cookies in gallery-dl's configuration file.
"""
        ttk.Label(content, text=instructions, justify='left').pack(anchor='w', pady=(5, 10))
        
        # gallery-dl info
        info_frame = ttk.Frame(content, relief='solid', borderwidth=1, padding=10)
        info_frame.pack(fill='x', pady=(10, 5))
        ttk.Label(info_frame, text="ℹ️ About gallery-dl:", 
                 font=('TkDefaultFont', 10, 'bold'), foreground='#3498db').pack(anchor='w')
        ttk.Label(info_frame, text="""gallery-dl is a command-line program to download image galleries
and media from multiple websites, including Reddit.

Documentation:""",
                 justify='left', wraplength=550).pack(anchor='w', pady=(2, 2))
        
        link_frame = ttk.Frame(info_frame)
        link_frame.pack(anchor='w', padx=10)
        link = tk.Text(link_frame, height=1, width=50, wrap='none', relief='flat',
                      bg=info_frame.cget('bg'), font=('TkDefaultFont', 9), cursor='hand2')
        link.insert('1.0', 'https://github.com/mikf/gallery-dl')
        link.config(state='disabled', fg='blue')
        link.pack(side='left')
        link.bind('<Button-1>', lambda e: self._copy_and_open('https://github.com/mikf/gallery-dl'))
        
        ttk.Label(info_frame, text="   (Click to copy and open)", 
                 foreground='gray', font=('TkDefaultFont', 8)).pack(anchor='w', padx=10)
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def _show_twitter_api_help(self):
        """Show instructions for obtaining Twitter API credentials with clickable links"""
        # Create a custom dialog with clickable links
        dialog = tk.Toplevel(self.root)
        dialog.title("Twitter/X API Help")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Content
        content = ttk.Frame(scrollable_frame, padding=10)
        content.pack(fill='both', expand=True)
        
        ttk.Label(content, text="📝 How to Get Twitter/X API Credentials", 
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        
        # Warning
        warning_frame = ttk.Frame(content, relief='solid', borderwidth=1, padding=10)
        warning_frame.pack(fill='x', pady=(5, 10))
        
        ttk.Label(warning_frame, text="⚠️ Twitter API Access Requirements:", 
                 font=('TkDefaultFont', 10, 'bold'), foreground='orange').pack(anchor='w')
        ttk.Label(warning_frame, text="""
• Free tier is very limited (read-only, low rate limits)
• Basic tier ($100/month) recommended for scraping
• You need a Twitter Developer Account""",
                 justify='left').pack(anchor='w', pady=(2, 0))
        
        # Step 1 with clickable link
        ttk.Label(content, text="1. Go to Twitter Developer Portal:", 
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=(10, 2))
        
        link1_frame = ttk.Frame(content)
        link1_frame.pack(anchor='w', padx=20)
        link1 = tk.Text(link1_frame, height=1, width=50, wrap='none', relief='flat', 
                       bg=dialog.cget('bg'), font=('TkDefaultFont', 9), cursor='hand2')
        link1.insert('1.0', 'https://developer.twitter.com/')
        link1.config(state='disabled', fg='blue')
        link1.pack(side='left')
        link1.bind('<Button-1>', lambda e: self._copy_and_open('https://developer.twitter.com/'))
        
        ttk.Label(content, text="   (Click to copy and open)", 
                 foreground='gray', font=('TkDefaultFont', 8)).pack(anchor='w', padx=20)
        
        # Instructions
        instructions = """
2. Sign up for a Developer Account:
   • Click "Sign up" in the top right
   • Apply for a developer account
   • Fill out the application form
   • Wait for approval (usually instant to 24 hours)

3. Create a Project & App:
   • Go to Developer Portal
   • Create a new Project
   • Create a new App within the Project

4. Generate Keys:
   • Go to your App's "Keys and tokens" tab
   • Generate/Regenerate:
     - API Key & API Secret
     - Bearer Token
     - Access Token & Access Token Secret

5. Copy all credentials to Settings tab:
   • Bearer Token (required for Twitter API v2)
   • API Key, API Secret
   • Access Token, Access Token Secret
"""
        ttk.Label(content, text=instructions, justify='left').pack(anchor='w', pady=(10, 5))
        
        # Note
        note_frame = ttk.Frame(content, relief='solid', borderwidth=1, padding=10)
        note_frame.pack(fill='x', pady=(10, 5))
        ttk.Label(note_frame, text="💡 Alternative Option:", 
                 font=('TkDefaultFont', 10, 'bold'), foreground='#3498db').pack(anchor='w')
        ttk.Label(note_frame, text="""For free tier limitations, consider using alternative Twitter scrapers
or third-party tools that don't require paid API access.""",
                 wraplength=600, justify='left').pack(anchor='w', pady=(2, 0))
        
        # Security note
        security_frame = ttk.Frame(content, relief='solid', borderwidth=1, padding=10)
        security_frame.pack(fill='x', pady=(10, 5))
        ttk.Label(security_frame, text="🔒 Security Note:", 
                 font=('TkDefaultFont', 10, 'bold'), foreground='#27ae60').pack(anchor='w')
        ttk.Label(security_frame, text="Keep all tokens private! Never share them publicly.",
                 wraplength=600).pack(anchor='w', pady=(2, 0))
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Close button
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def _copy_and_open(self, url):
        """Copy URL to clipboard and open in browser"""
        import webbrowser
        try:
            # Copy to clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            # Open in browser
            webbrowser.open(url)
            self.log(f"📋 Copied and opened: {url}")
        except Exception as e:
            self.log(f"Error opening URL: {e}")
            messagebox.showinfo("URL", f"Link:\n\n{url}\n\nCopied to clipboard!")
    
    def _show_onlyfans_api_help(self):
        """Show instructions for obtaining OnlyFans API access"""
        help_text = """📝 OnlyFans API Access (Advanced Users)

⚠️ WARNING: Direct OnlyFans API access is complex and may violate their Terms of Service.
OF-DL is the recommended method for most users.

If OF-DL stops working and you need direct API access:

Method 1: Browser Developer Tools (Easiest)
═══════════════════════════════════════════

1. Log into OnlyFans in your browser (Chrome/Firefox)

2. Open Developer Tools (F12)

3. Go to "Network" tab

4. Click on any OnlyFans request

5. Look for these headers:
   • Cookie: (contains auth_id and sess values)
   • User-Agent: Your browser's user agent
   • x-bc: Browser fingerprint token

6. Important values to extract:
   • sess: Session token
   • auth_id: Authentication ID
   • user-agent: Browser identifier
   • x-bc: Security token

Method 2: Manual API Calls
═══════════════════════════

OnlyFans uses these endpoints:
• https://onlyfans.com/api2/v2/users/me
• https://onlyfans.com/api2/v2/subscriptions/subscribes
• https://onlyfans.com/api2/v2/posts/{userId}

Required headers for API calls:
• Cookie: auth_id={your_auth_id}; sess={your_sess};
• User-Agent: {your_browser_user_agent}
• x-bc: {browser_checksum}
• Accept: application/json

⚠️ IMPORTANT NOTES:
═══════════════════

• Session tokens expire regularly (need to re-extract)
• OnlyFans actively blocks automated access
• This may violate OnlyFans Terms of Service
• Account suspension risk if detected
• Headers change frequently - no guarantee this will work

RECOMMENDATION:
═══════════════

Use OF-DL (https://git.ofdl.tools/sim0n00ps/OF-DL) instead:
✓ Handles authentication automatically
✓ Uses browser-based login (more reliable)
✓ Maintained by the community
✓ Updates when OnlyFans changes API

Only attempt direct API access if:
• You understand the risks
• OF-DL is not working
• You have programming experience
• You accept potential account suspension

For most users, waiting for OF-DL updates is safer.
"""
        messagebox.showinfo("OnlyFans API Access", help_text)
    
    def _copy_email_to_clipboard(self):
        """Copy email address to clipboard and show confirmation"""
        email = "MyMediaScraperBot@gmail.com"
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(email)
            messagebox.showinfo("Email Copied", 
                              f"Email address copied to clipboard:\n\n{email}\n\nFeel free to reach out with questions, issues, or suggestions!")
        except Exception as e:
            messagebox.showinfo("Contact Information", 
                              f"For updates or issues, contact:\n\n{email}")
    
    def _open_donation_link(self):
        """Open Buy Me a Coffee donation page in browser"""
        import webbrowser
        url = "https://buymeacoffee.com/sknight"
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showinfo("Donation Link", 
                              f"Please visit:\n\n{url}\n\nThank you for your support!")
    
    def _show_about(self):
        """Show about dialog"""
        about_text = """🎬 Media Scraper Bot v2.0

A comprehensive media downloader for:
• Reddit (subreddits & users)
• Twitter/X (user timelines)
• Websites (any URL)
• OnlyFans (via OF-DL)

Features:
✓ 100% Duplicate Detection (SHA256)
✓ Active/Inactive User Management
✓ Download History Tracking
✓ Folder Organization
✓ Discord Bot Integration

Created with ❤️ for archiving
"""
        messagebox.showinfo("About Media Scraper Bot", about_text)
    
    def show_statistics(self):
        """Show comprehensive statistics"""
        # User counts
        stats = self.user_manager.get_statistics()
        
        # History stats
        history_stats = {
            'reddit': len(self.download_history.history.get('reddit', {})),
            'twitter': len(self.download_history.history.get('twitter', {})),
            'websites': len(self.download_history.history.get('websites', {}))
        }
        
        # Duplicate checker stats
        total_files = len(self.duplicate_checker.file_hashes)
        
        stats_text = f"""📊 Statistics

User Management:
Reddit Users: {stats['reddit']['active']} active, {stats['reddit']['inactive']} inactive
Subreddits: {stats['subreddits']['active']} active, {stats['subreddits']['inactive']} inactive
Twitter Users: {stats['twitter']['active']} active, {stats['twitter']['inactive']} inactive
Websites: {stats['websites']['active']} active, {stats['websites']['inactive']} inactive

Download History:
Reddit: {history_stats['reddit']} tracked posts
Twitter: {history_stats['twitter']} tracked tweets
Websites: {history_stats['websites']} tracked URLs

Duplicate Detection:
{total_files} unique files tracked by SHA256 hash
"""
        messagebox.showinfo("Statistics", stats_text)
    
    # List management methods
    def refresh_subreddit_lists(self):
        """Refresh subreddit active/inactive listboxes"""
        self.subreddit_active_listbox.delete(0, tk.END)
        self.subreddit_inactive_listbox.delete(0, tk.END)
        
        for item in self.user_manager.get_active_users('subreddits'):
            self.subreddit_active_listbox.insert(tk.END, item)
        
        for item in self.user_manager.get_inactive_users('subreddits'):
            self.subreddit_inactive_listbox.insert(tk.END, item)
    
    def refresh_reddit_user_lists(self):
        """Refresh Reddit user active/inactive listboxes"""
        self.reddit_user_active_listbox.delete(0, tk.END)
        self.reddit_user_inactive_listbox.delete(0, tk.END)
        
        for item in self.user_manager.get_active_users('reddit'):
            self.reddit_user_active_listbox.insert(tk.END, item)
        
        for item in self.user_manager.get_inactive_users('reddit'):
            self.reddit_user_inactive_listbox.insert(tk.END, item)
    
    def refresh_twitter_user_lists(self):
        """Refresh Twitter user active/inactive listboxes"""
        self.twitter_user_active_listbox.delete(0, tk.END)
        self.twitter_user_inactive_listbox.delete(0, tk.END)
        
        for item in self.user_manager.get_active_users('twitter'):
            self.twitter_user_active_listbox.insert(tk.END, item)
        
        for item in self.user_manager.get_inactive_users('twitter'):
            self.twitter_user_inactive_listbox.insert(tk.END, item)
    
    def refresh_website_lists(self):
        """Refresh website active/inactive listboxes"""
        self.website_active_listbox.delete(0, tk.END)
        self.website_inactive_listbox.delete(0, tk.END)
        
        for item in self.user_manager.get_active_users('websites'):
            self.website_active_listbox.insert(tk.END, item)
        
        for item in self.user_manager.get_inactive_users('websites'):
            self.website_inactive_listbox.insert(tk.END, item)
    
    # Move methods for Active/Inactive
    def move_subreddit_to_inactive(self):
        """Move selected subreddit from active to inactive"""
        selections = self.subreddit_active_listbox.curselection()
        for idx in selections:
            subreddit = self.subreddit_active_listbox.get(idx)
            self.user_manager.move_to_inactive('subreddits', subreddit)
            self.log(f"Moved subreddit to inactive: {subreddit}")
        self.refresh_subreddit_lists()
    
    def move_subreddit_to_active(self):
        """Move selected subreddit from inactive to active"""
        selections = self.subreddit_inactive_listbox.curselection()
        for idx in selections:
            subreddit = self.subreddit_inactive_listbox.get(idx)
            self.user_manager.move_to_active('subreddits', subreddit)
            self.log(f"Moved subreddit to active: {subreddit}")
        self.refresh_subreddit_lists()
    
    def move_reddit_user_to_inactive(self):
        """Move selected Reddit user from active to inactive"""
        selections = self.reddit_user_active_listbox.curselection()
        for idx in selections:
            username = self.reddit_user_active_listbox.get(idx)
            self.user_manager.move_to_inactive('reddit', username)
            self.log(f"Moved Reddit user to inactive: {username}")
        self.refresh_reddit_user_lists()
    
    def move_reddit_user_to_active(self):
        """Move selected Reddit user from inactive to active"""
        selections = self.reddit_user_inactive_listbox.curselection()
        for idx in selections:
            username = self.reddit_user_inactive_listbox.get(idx)
            self.user_manager.move_to_active('reddit', username)
            self.log(f"Moved Reddit user to active: {username}")
        self.refresh_reddit_user_lists()
    
    # Add/Remove methods
    def add_subreddit(self):
        """Add subreddit to active list"""
        subreddit = self.subreddit_entry.get().strip()
        if subreddit:
            if self.user_manager.add_user('subreddits', subreddit, active=True):
                self.refresh_subreddit_lists()
                self.subreddit_entry.delete(0, tk.END)
                self.log(f"Added subreddit: {subreddit}")
            else:
                messagebox.showinfo("Info", "Subreddit already exists")
    
    def remove_subreddit(self):
        """Remove selected subreddit from both lists"""
        # Check active list first
        selections = self.subreddit_active_listbox.curselection()
        if selections:
            for idx in selections:
                subreddit = self.subreddit_active_listbox.get(idx)
                self.user_manager.remove_user('subreddits', subreddit)
                self.log(f"Removed subreddit: {subreddit}")
            self.refresh_subreddit_lists()
            return
        
        # Check inactive list
        selections = self.subreddit_inactive_listbox.curselection()
        if selections:
            for idx in selections:
                subreddit = self.subreddit_inactive_listbox.get(idx)
                self.user_manager.remove_user('subreddits', subreddit)
                self.log(f"Removed subreddit: {subreddit}")
            self.refresh_subreddit_lists()
    
    def add_reddit_user(self):
        """Add Reddit user to active list"""
        username = self.reddit_user_entry.get().strip()
        if username:
            if self.user_manager.add_user('reddit', username, active=True):
                self.refresh_reddit_user_lists()
                self.reddit_user_entry.delete(0, tk.END)
                self.log(f"Added Reddit user: {username}")
            else:
                messagebox.showinfo("Info", "User already exists")
    
    def remove_reddit_user(self):
        """Remove selected Reddit user from both lists"""
        # Check active list first
        selections = self.reddit_user_active_listbox.curselection()
        if selections:
            for idx in selections:
                username = self.reddit_user_active_listbox.get(idx)
                self.user_manager.remove_user('reddit', username)
                self.log(f"Removed Reddit user: {username}")
            self.refresh_reddit_user_lists()
            return
        
        # Check inactive list
        selections = self.reddit_user_inactive_listbox.curselection()
        if selections:
            for idx in selections:
                username = self.reddit_user_inactive_listbox.get(idx)
                self.user_manager.remove_user('reddit', username)
                self.log(f"Removed Reddit user: {username}")
            self.refresh_reddit_user_lists()
    
    def move_twitter_user_to_inactive(self):
        """Move selected Twitter user from active to inactive"""
        selections = self.twitter_user_active_listbox.curselection()
        for idx in selections:
            username = self.twitter_user_active_listbox.get(idx)
            self.user_manager.move_to_inactive('twitter', username)
            self.log(f"Moved Twitter user to inactive: {username}")
        self.refresh_twitter_user_lists()
    
    def move_twitter_user_to_active(self):
        """Move selected Twitter user from inactive to active"""
        selections = self.twitter_user_inactive_listbox.curselection()
        for idx in selections:
            username = self.twitter_user_inactive_listbox.get(idx)
            self.user_manager.move_to_active('twitter', username)
            self.log(f"Moved Twitter user to active: {username}")
        self.refresh_twitter_user_lists()
    
    def move_website_to_inactive(self):
        """Move selected website from active to inactive"""
        selections = self.website_active_listbox.curselection()
        for idx in selections:
            website = self.website_active_listbox.get(idx)
            self.user_manager.move_to_inactive('websites', website)
            self.log(f"Moved website to inactive: {website}")
        self.refresh_website_lists()
    
    def move_website_to_active(self):
        """Move selected website from inactive to active"""
        selections = self.website_inactive_listbox.curselection()
        for idx in selections:
            website = self.website_inactive_listbox.get(idx)
            self.user_manager.move_to_active('websites', website)
            self.log(f"Moved website to active: {website}")
        self.refresh_website_lists()
    
    def add_twitter_user(self):
        """Add Twitter user to active list"""
        raw = self.twitter_user_entry.get().strip()
        if not raw:
            return
        # Normalize: strip @, extract handle from full URL, remove query/fragment
        handle = raw.lstrip('@')
        if handle.startswith('http://') or handle.startswith('https://'):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(handle)
                segments = [seg for seg in parsed.path.split('/') if seg]
                if segments:
                    handle = segments[0]
            except Exception:
                pass
        handle = handle.split('?')[0].split('#')[0]
        # Replace invalid chars with underscore (align with twitter_scraper normalization)
        import re
        norm = re.sub(r'[^A-Za-z0-9_]', '_', handle) or 'user'
        if self.user_manager.add_user('twitter', norm, active=True):
            self.refresh_twitter_user_lists()
            self.twitter_user_entry.delete(0, tk.END)
            self.log(f"Added Twitter user: {norm} (from input: {raw})")
        else:
            messagebox.showinfo("Info", "User already exists")
    
    def remove_twitter_user(self):
        """Remove selected Twitter user from both lists"""
        # Check active list first
        selections = self.twitter_user_active_listbox.curselection()
        if selections:
            for idx in selections:
                username = self.twitter_user_active_listbox.get(idx)
                self.user_manager.remove_user('twitter', username)
                self.log(f"Removed Twitter user: {username}")
            self.refresh_twitter_user_lists()
            return
        
        # Check inactive list
        selections = self.twitter_user_inactive_listbox.curselection()
        if selections:
            for idx in selections:
                username = self.twitter_user_inactive_listbox.get(idx)
                self.user_manager.remove_user('twitter', username)
                self.log(f"Removed Twitter user: {username}")
            self.refresh_twitter_user_lists()
    
    def add_website(self):
        """Add website to active list"""
        url = self.website_entry.get().strip()
        if url:
            if not url.startswith('http'):
                url = 'https://' + url
            if self.user_manager.add_user('websites', url, active=True):
                self.refresh_website_lists()
                self.website_entry.delete(0, tk.END)
                self.log(f"Added website: {url}")
            else:
                messagebox.showinfo("Info", "Website already exists")
    
    def remove_website(self):
        """Remove selected website from both lists"""
        # Check active list first
        selections = self.website_active_listbox.curselection()
        if selections:
            for idx in selections:
                url = self.website_active_listbox.get(idx)
                self.user_manager.remove_user('websites', url)
                self.log(f"Removed website: {url}")
            self.refresh_website_lists()
            return
        
        # Check inactive list
        selections = self.website_inactive_listbox.curselection()
        if selections:
            for idx in selections:
                url = self.website_inactive_listbox.get(idx)
                self.user_manager.remove_user('websites', url)
                self.log(f"Removed website: {url}")
            self.refresh_website_lists()
    
    # Settings methods
    def browse_download_path(self):
        """Browse for download directory"""
        path = filedialog.askdirectory()
        if path:
            self.download_path.delete(0, tk.END)
            self.download_path.insert(0, path)
    
    def save_settings(self):
        """Save settings to config file"""
        # Reddit settings removed - gallery-dl doesn't need API credentials
        
        self.config.set('twitter.bearer_token', self.twitter_bearer.get())
        self.config.set('twitter.api_key', self.twitter_api_key.get())
        self.config.set('twitter.api_secret', self.twitter_api_secret.get())
        self.config.set('twitter.access_token', self.twitter_access_token.get())
        self.config.set('twitter.access_token_secret', self.twitter_access_secret.get())
        
        # OnlyFans OF-DL path
        self.config.set('onlyfans.ofdl_path', self.ofdl_exe_path.get())
        
        # OnlyFans Download Options
        self.config.set('onlyfans.download_posts', self.of_download_posts.get())
        self.config.set('onlyfans.download_paid_posts', self.of_download_paid_posts.get())
        self.config.set('onlyfans.download_messages', self.of_download_messages.get())
        self.config.set('onlyfans.download_paid_messages', self.of_download_paid_messages.get())
        self.config.set('onlyfans.download_stories', self.of_download_stories.get())
        self.config.set('onlyfans.download_highlights', self.of_download_highlights.get())
        self.config.set('onlyfans.download_archived', self.of_download_archived.get())
        self.config.set('onlyfans.download_streams', self.of_download_streams.get())
        self.config.set('onlyfans.download_images', self.of_download_images.get())
        self.config.set('onlyfans.download_videos', self.of_download_videos.get())
        self.config.set('onlyfans.download_audios', self.of_download_audios.get())
        self.config.set('onlyfans.download_avatar_header', self.of_download_avatar_header.get())
        self.config.set('onlyfans.folder_per_post', self.of_folder_per_post.get())
        self.config.set('onlyfans.folder_per_paid_post', self.of_folder_per_paid_post.get())
        self.config.set('onlyfans.folder_per_message', self.of_folder_per_message.get())
        self.config.set('onlyfans.folder_per_paid_message', self.of_folder_per_paid_message.get())
        self.config.set('onlyfans.skip_ads', self.of_skip_ads.get())
        self.config.set('onlyfans.ignore_own_messages', self.of_ignore_own_messages.get())
        self.config.set('onlyfans.include_expired', self.of_include_expired.get())
        self.config.set('onlyfans.include_restricted', self.of_include_restricted.get())
        self.config.set('onlyfans.download_duplicates', self.of_download_duplicates.get())
        self.config.set('onlyfans.download_incrementally', self.of_download_incrementally.get())
        
        self.config.set('downloads.base_path', self.download_path.get())
        self.config.set('downloads.redownload_deleted_files', self.redownload_deleted.get())
        
        # Reset scrapers to use new credentials
        self.reddit_scraper = None
        self.twitter_scraper = None
        
        messagebox.showinfo("Success", "Settings saved successfully")
        self.log("Settings saved")
    
    # Scraping methods
    def toggle_pause(self):
        """Pause or resume the current scraping task"""
        if not self.is_downloading:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_button.config(text="▶ Resume")
            self.log("Scraping paused")
        else:
            self.pause_button.config(text="⏸ Pause")
            self.update_status("Resuming...")
            self.log("Scraping resumed")

    def scrape_all_subreddits(self):
        """Scrape all ACTIVE subreddits only"""
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress")
            return
        
        subreddits = self.user_manager.get_active_users('subreddits')
        if not subreddits:
            messagebox.showinfo("Info", "No active subreddits to scrape")
            return
        
        thread = threading.Thread(target=self._scrape_subreddits_thread, args=(subreddits,))
        thread.daemon = True
        thread.start()
    
    def _scrape_subreddits_thread(self, subreddits):
        """Thread for scraping subreddits"""
        self.is_downloading = True
        self.is_paused = False
        self.pause_button['state'] = 'normal'
        self.pause_button.config(text="⏸ Pause")
        self.update_status("Initializing Reddit scraper...")
        
        # Get date range from UI
        start_date_str = self.subreddit_start_date.get().strip()
        end_date_str = self.subreddit_end_date.get().strip()
        
        # Parse dates if provided
        start_date = None
        end_date = None
        
        if start_date_str and start_date_str != "YYYY-MM-DD":
            try:
                from datetime import datetime
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                self.log(f"📅 Using start date: {start_date_str}")
            except ValueError:
                self.log(f"⚠️ Invalid start date format: {start_date_str}, ignoring")
        
        if end_date_str and end_date_str != "YYYY-MM-DD":
            try:
                from datetime import datetime
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                self.log(f"📅 Using end date: {end_date_str}")
            except ValueError:
                self.log(f"⚠️ Invalid end date format: {end_date_str}, ignoring")
        
        # Send Discord notification that scraping started
        date_info = ""
        if start_date or end_date:
            date_info = f" (from {start_date_str if start_date else 'beginning'} to {end_date_str if end_date else 'now'})"
        
        try:
            if not self.reddit_scraper:
                self.reddit_scraper = RedditScraper(
                    self.config.get('reddit.client_id'),
                    self.config.get('reddit.client_secret'),
                    self.config.get('reddit.user_agent'),
                    history=self.download_history,
                    duplicate_checker=self.duplicate_checker
                )
            
            base_path = self.config.get('downloads.base_path', 'Downloads')
            total_subreddits = len(subreddits)
            self.start_progress(total_subreddits)
            
            # Initialize Reddit tab progress
            self.reddit_progress_bar['maximum'] = total_subreddits
            total_downloaded = 0
            
            for idx, subreddit in enumerate(subreddits):
                # Check for pause
                while self.is_paused:
                    self.update_status("⏸ Paused - Click Resume to continue")
                    time.sleep(0.5)
                
                self.update_status(f"Scraping r/{subreddit}...")
                self.reddit_current_op_var.set(f"Scraping r/{subreddit}...")
                self.reddit_progress_var.set(idx)
                percentage = ((idx) / total_subreddits) * 100
                self.reddit_progress_text_var.set(f"{idx} / {total_subreddits} subreddits ({percentage:.1f}%)")
                self.log(f"Starting scrape of r/{subreddit}")
                
                # Get sorting and limit settings
                sort_by = self.subreddit_sort_var.get()
                limit = None if self.subreddit_unlimited_var.get() else self.subreddit_limit_var.get()
                
                downloaded = self.reddit_scraper.scrape_subreddit(
                    subreddit, base_path, limit=limit, progress_callback=self.log,
                    start_date=start_date, end_date=end_date, sort_by=sort_by
                )
                
                total_downloaded += len(downloaded)
                self.log(f"Downloaded {len(downloaded)} files from r/{subreddit}")
                self.reddit_details_var.set(f"Total files downloaded: {total_downloaded}")
                self.update_progress(idx + 1)
            
            # Final update
            self.reddit_progress_var.set(total_subreddits)
            self.reddit_progress_text_var.set(f"{total_subreddits} / {total_subreddits} subreddits (100%)")
            self.reddit_current_op_var.set("Scraping complete!")
            self.reddit_details_var.set(f"Total files downloaded: {total_downloaded}")
            
            # Send Discord completion notification
            
            # Auto-organize downloads if enabled
            if bool(self.config.get('downloads.auto_organize_after_scrape', True)):
                self.log("Auto-organizing downloads into subfolders...")
                self.organize_downloads()
            
            self.end_progress()
            self.update_status("Scraping complete!")
            self.log("All subreddits scraped successfully")
        
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status("Error occurred during scraping")
            self.end_progress()
        
        finally:
            self.is_downloading = False
            self.is_paused = False
            if hasattr(self, 'pause_button'):
                self.pause_button['state'] = 'disabled'
                self.pause_button.config(text="⏸ Pause")
    
    def scrape_all_reddit_users(self):
        """Scrape all ACTIVE Reddit users only"""
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress")
            return
        
        reddit_users = self.user_manager.get_active_users('reddit')
        
        if not reddit_users:
            messagebox.showinfo("Info", "No active Reddit users to scrape")
            return
        
        thread = threading.Thread(target=self._scrape_reddit_users_thread, args=(reddit_users,))
        thread.daemon = True
        thread.start()
    
    def _scrape_reddit_users_thread(self, users):
        """Thread for scraping Reddit users"""
        self.is_downloading = True
        self.is_paused = False
        self.pause_button['state'] = 'normal'
        self.pause_button.config(text="⏸ Pause")
        self.update_status("Initializing Reddit scraper...")
        
        # Send Discord notification to general channel that scraping started
        
        try:
            if not self.reddit_scraper:
                self.reddit_scraper = RedditScraper(
                    self.config.get('reddit.client_id'),
                    self.config.get('reddit.client_secret'),
                    self.config.get('reddit.user_agent'),
                    history=self.download_history,
                    duplicate_checker=self.duplicate_checker
                )
            
            base_path = self.config.get('downloads.base_path', 'Downloads')
            total_users = len(users)
            self.start_progress(total_users)
            
            # Initialize Reddit tab progress
            self.reddit_progress_bar['maximum'] = total_users
            total_downloaded = 0
            
            for idx, username in enumerate(users):
                while self.is_paused:
                    self.update_status("⏸ Paused - Click Resume to continue")
                    time.sleep(0.5)
                
                self.update_status(f"Scraping u/{username}...")
                self.reddit_current_op_var.set(f"Scraping u/{username}...")
                self.reddit_progress_var.set(idx)
                percentage = ((idx) / total_users) * 100
                self.reddit_progress_text_var.set(f"{idx} / {total_users} users ({percentage:.1f}%)")
                self.log(f"Starting scrape of u/{username}")
                
                # Check unlimited flag
                unlimited = getattr(self, 'reddit_user_unlimited_var', None)
                if unlimited and unlimited.get():
                    limit = None
                    self.log("⚡ Unlimited mode: scanning all posts from beginning of time...")
                else:
                    post_limit = getattr(self, 'reddit_user_limit_var', None)
                    limit = post_limit.get() if post_limit else 100
                
                downloaded = self.reddit_scraper.scrape_user(
                    username, base_path, limit=limit, progress_callback=self.log
                )
                
                total_downloaded += len(downloaded)
                self.log(f"Downloaded {len(downloaded)} files from u/{username}")
                self.reddit_details_var.set(f"Total files downloaded: {total_downloaded}")
                self.update_progress(idx + 1)
            
            # Final update
            self.reddit_progress_var.set(total_users)
            self.reddit_progress_text_var.set(f"{total_users} / {total_users} users (100%)")
            self.reddit_current_op_var.set("Scraping complete!")
            self.reddit_details_var.set(f"Total files downloaded: {total_downloaded}")
            
            # Send Discord notifications
            if total_downloaded > 0:
                download_msg = f"📥 **Reddit Scrape Complete**\n"
                download_msg += f"• Users Scraped: {total_users}\n"
                download_msg += f"• Files Downloaded: {total_downloaded}"
            
            # Auto-organize downloads if enabled
            if bool(self.config.get('downloads.auto_organize_after_scrape', True)):
                self.log("Auto-organizing downloads into subfolders...")
                self.organize_downloads()
            
            self.end_progress()
            self.update_status("Scraping complete!")
            self.log("All Reddit users scraped successfully")
        
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status("Error occurred during scraping")
            self.end_progress()
        
        finally:
            self.is_downloading = False
            self.is_paused = False
            if hasattr(self, 'pause_button'):
                self.pause_button['state'] = 'disabled'
                self.pause_button.config(text="⏸ Pause")
    
    def scrape_all_twitter_users(self):
        """Scrape all ACTIVE Twitter users only"""
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress")
            return
        
        twitter_users = self.user_manager.get_active_users('twitter')
        
        if not twitter_users:
            messagebox.showinfo("Info", "No active Twitter users to scrape")
            return
        
        thread = threading.Thread(target=self._scrape_twitter_users_thread, args=(twitter_users,))
        thread.daemon = True
        thread.start()
    
    def _scrape_twitter_users_thread(self, users):
        """Thread for scraping Twitter users"""
        self.is_downloading = True
        self.is_paused = False
        if hasattr(self, 'pause_button'):
            self.pause_button['state'] = 'normal'
            self.pause_button.config(text="⏸ Pause")
        self.update_status("Initializing Twitter scraper...")
        
        try:
            # Normalize any stored usernames (handle legacy entries with full URLs or leading @)
            normalized = []
            import re
            from urllib.parse import urlparse
            for u in users:
                raw = u.strip()
                raw = raw.lstrip('@')
                if raw.startswith('http://') or raw.startswith('https://'):
                    try:
                        parsed = urlparse(raw)
                        segments = [seg for seg in parsed.path.split('/') if seg]
                        if segments:
                            raw = segments[0]
                    except Exception:
                        pass
                raw = raw.split('?')[0].split('#')[0]
                cleaned = re.sub(r'[^A-Za-z0-9_]', '_', raw) or 'user'
                normalized.append(cleaned)
            # If normalization changed any, update user_manager storage (avoid duplicates)
            if set(normalized) != set(users):
                # Remove all old entries and re-add normalized unique ones as active
                for old in users:
                    self.user_manager.remove_user('twitter', old)
                for new in sorted(set(normalized)):
                    self.user_manager.add_user('twitter', new, active=True)
                users = sorted(set(normalized))
                self.refresh_twitter_user_lists()
                self.log(f"Normalized Twitter usernames: {', '.join(users)}")
            if not self.twitter_scraper:
                bearer = self.config.get('twitter.bearer_token')
                api_key = self.config.get('twitter.api_key')
                api_secret = self.config.get('twitter.api_secret')
                access_token = self.config.get('twitter.access_token')
                access_secret = self.config.get('twitter.access_token_secret')
                
                self.twitter_scraper = TwitterScraper(
                    bearer_token=bearer if bearer else None,
                    api_key=api_key if api_key else None,
                    api_secret=api_secret if api_secret else None,
                    access_token=access_token if access_token else None,
                    access_token_secret=access_secret if access_secret else None,
                    history=self.download_history,
                    duplicate_checker=self.duplicate_checker
                )
            
            base_path = self.config.get('downloads.base_path', 'Downloads')
            total_users = len(users)
            self.start_progress(total_users)
            
            for idx, username in enumerate(users):
                while self.is_paused:
                    self.update_status("⏸ Paused - Click Resume to continue")
                    time.sleep(0.5)
                
                self.update_status(f"Scraping @{username}...")
                self.log(f"Starting scrape of @{username}")
                
                # Check unlimited flag
                unlimited = getattr(self, 'twitter_unlimited_var', None)
                if unlimited and unlimited.get():
                    limit = None  # type: ignore  # No limit
                    self.log("⚡ Unlimited mode: scanning all tweets from beginning of time...")
                else:
                    tweet_limit = getattr(self, 'twitter_limit_var', None)
                    limit = tweet_limit.get() if tweet_limit else 500
                downloaded = self.twitter_scraper.scrape_user(
                    username, base_path, limit=limit, progress_callback=self.log
                )
                
                self.log(f"Downloaded {len(downloaded)} files from @{username}")
                self.update_progress(idx + 1)
            
            # Auto-organize downloads if enabled
            if bool(self.config.get('downloads.auto_organize_after_scrape', True)):
                self.log("Auto-organizing downloads into subfolders...")
                self.organize_downloads()
            
            self.end_progress()
            self.update_status("Scraping complete!")
            self.log("All Twitter users scraped successfully")
            
            # Send Discord notification
            total_downloaded = sum(len(self.twitter_scraper.scrape_user(u, base_path, limit=0, progress_callback=None)) for u in [])
        
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status("Error occurred during scraping")
            self.end_progress()
        
        finally:
            self.is_downloading = False
            self.is_paused = False
            if hasattr(self, 'pause_button'):
                self.pause_button['state'] = 'disabled'
                self.pause_button.config(text="⏸ Pause")
    
    def scrape_all_websites(self):
        """Scrape all ACTIVE websites and download automatically"""
        if self.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress")
            return
        
        websites = self.user_manager.get_active_users('websites')
        if not websites:
            messagebox.showinfo("Info", "No active websites to scrape")
            return
        
        # Check if there are completed websites - offer to resume or start fresh
        completed = self.website_scrape_state.get('completed_websites', [])
        remaining = [w for w in websites if w not in completed]
        
        resume_mode = False
        if completed and remaining:
            # Some websites completed, some remaining
            result = messagebox.askyesnocancel(
                "Resume Scraping?",
                f"Found {len(completed)} completed website(s) and {len(remaining)} remaining.\n\n" +
                "Yes = Resume from where you left off\n" +
                "No = Start fresh (clear history)\n" +
                "Cancel = Don't scrape"
            )
            if result is None:  # Cancel
                return
            elif result:  # Yes - Resume
                resume_mode = True
                self.log(f"📋 Resuming: {len(remaining)} websites remaining")
            else:  # No - Start fresh
                self._clear_website_scrape_state()
                self.log("🔄 Starting fresh - history cleared")
        elif completed and not remaining:
            # All websites completed - just check for new content without prompting
            self.log("✓ All websites previously scraped - checking for new content only")
            resume_mode = True
        else:
            # No completed websites - fresh start
            self._clear_website_scrape_state()
        
        thread = threading.Thread(target=self._scrape_websites_thread, args=(websites, resume_mode))
        thread.daemon = True
        thread.start()
    

    def _scrape_websites_thread(self, websites, resume_mode=False):
        """Thread for scraping websites
        
        Args:
            websites: List of all websites
            resume_mode: If True, skip already completed websites
        """
        self.is_downloading = True
        self.is_paused = False
        if hasattr(self, 'pause_button'):
            self.pause_button['state'] = 'normal'
            self.pause_button.config(text="⏸ Pause")
        
        try:
            base_path = self.config.get('downloads.base_path', 'Downloads')

            # Queue for discovered media (persists between runs)
            queue_path = os.path.join(self.botfiles_dir, 'download_queue.json')
            download_queue = DownloadQueue(queue_path)
            existing_pending = len(download_queue.as_list())
            if existing_pending:
                self.log(f"Pending downloads from previous run: {existing_pending}")
            
            # Filter websites based on resume mode
            completed = self.website_scrape_state.get('completed_websites', [])
            if resume_mode:
                websites_to_scrape = [w for w in websites if w not in completed]
                self.log(f"📋 Resume mode: Skipping {len(completed)} completed websites")
                self.update_status(f"Resuming: {len(websites_to_scrape)} websites remaining...")
            else:
                websites_to_scrape = websites
                self.update_status("Starting website scraping...")
            
            if not websites_to_scrape:
                self.log("No websites to scrape")
                return
            

            # Get max_pages, scroll_count, and workers from UI
            try:
                max_pages = int(self.website_max_pages.get())
            except Exception:
                max_pages = 10

            try:
                scroll_count = int(self.website_scroll_count.get())
            except Exception:
                scroll_count = 5
            
            try:
                workers = int(self.website_workers.get())
                workers = max(1, min(workers, 20))  # Clamp between 1 and 20
            except Exception:
                workers = 5
            
            # Reinitialize website scraper with new worker count
            self.website_scraper = WebsiteScraper(
                history=self.download_history,
                max_workers=workers,
                aggressive_popup=bool(self.website_aggressive_popup_var.get()),
                duplicate_checker=self.duplicate_checker
            )
            self.log(f"Aggressive popup removal: {'ON' if self.website_aggressive_popup_var.get() else 'OFF'}")
            self.log(f"Using {workers} concurrent workers for downloading")

            total_websites = len(websites_to_scrape)
            self.start_progress(total_websites)

            total_discovered = 0
            for idx, url in enumerate(websites_to_scrape):
                while self.is_paused:
                    self.update_status("⏸ Paused - Click Resume to continue")
                    time.sleep(0.5)
                
                # Mark as current website
                self.website_scrape_state['current_website'] = url
                self._save_website_scrape_state()

                self.update_status(f"Scanning {url[:60]}...")
                self.log(f"Scanning {url} for media (phase 1: discovery)")

                candidates = self.website_scraper.scrape_url(
                    url,
                    base_path,
                    progress_callback=self.log,
                    max_pages=max_pages,
                    scroll_count=scroll_count,
                    collect_only=True,
                )

                if candidates:
                    download_queue.extend(candidates)
                    total_discovered += len(candidates)
                    self.log(f"Queued {len(candidates)} media items from {url}")
                else:
                    self.log(f"No new media discovered on {url}")
                
                # Mark website as completed
                if url not in self.website_scrape_state['completed_websites']:
                    self.website_scrape_state['completed_websites'].append(url)
                    self._save_website_scrape_state()
                    self.log(f"✓ Completed: {url}")

                self.update_progress(idx + 1)

            self.end_progress()

            download_queue.ensure_unique('history_url')
            pending_total = len(download_queue.as_list())
            newly_added = max(0, pending_total - existing_pending)

            self.log(
                f"Discovery complete. Pending downloads: {pending_total} "
                f"(new queue entries: {newly_added}, discovered this run: {total_discovered})"
            )

            if pending_total == 0:
                self.update_status("No media queued for download.")
                return

            self.update_status("Starting downloads (phase 2)...")
            self.start_progress(pending_total)

            processed_count = 0

            def progress_hook(processed, succeeded):
                nonlocal processed_count
                processed_count = processed
                self.update_progress(min(processed_count, pending_total))

            downloads = self.website_scraper.process_download_queue(
                download_queue,
                progress_callback=self.log,
                pause_checker=lambda: self.is_paused,
                progress_hook=progress_hook,
            )

            self.end_progress()
            self.update_status("Downloads complete!" if downloads else "No new files downloaded.")
            self.log(f"Completed download phase: {len(downloads)} file(s) saved")
            
            # Clear current website marker
            self.website_scrape_state['current_website'] = None
            self._save_website_scrape_state()
            
            # Show completion summary
            completed_count = len(self.website_scrape_state['completed_websites'])
            self.log(f"📊 Session complete: {completed_count} websites fully processed")
            
            # Send Discord notification to downloads channel
            if downloads:
                total_size_mb = sum(os.path.getsize(f) / (1024 * 1024) for f in downloads if os.path.exists(f))
                download_msg = f"📥 **Website Scrape Complete**\n"
                download_msg += f"• Files Downloaded: {len(downloads)}\n"
                download_msg += f"• Total Size: {total_size_mb:.2f} MB\n"
                download_msg += f"• Websites Processed: {completed_count}"
            
            # Auto-organize downloads if enabled
            if downloads and bool(self.config.get('downloads.auto_organize_after_scrape', True)):
                self.log("Auto-organizing downloads into subfolders...")
                self.organize_downloads()
        
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status("Error occurred during scraping")
            self.end_progress()
            # Save state even on error so we can resume
            self._save_website_scrape_state()
        
        finally:
            self.is_downloading = False
            self.is_paused = False
            if hasattr(self, 'pause_button'):
                self.pause_button['state'] = 'disabled'
                self.pause_button.config(text="⏸ Pause")
    
    def scan_selected_website(self):
        """Scan selected website/sitemap to preview content"""
        # Check active list first
        selection = self.website_active_listbox.curselection()
        if selection:
            url_entry = self.website_active_listbox.get(selection[0])
        else:
            # Check inactive list
            selection = self.website_inactive_listbox.curselection()
            if selection:
                url_entry = self.website_inactive_listbox.get(selection[0])
            else:
                messagebox.showinfo("Info", "Please select a website to scan")
                return
        
        thread = threading.Thread(target=self._scan_website_thread, args=(url_entry,))
        thread.daemon = True
        thread.start()
    
    def _scan_website_thread(self, url_entry):
        """Thread for scanning a website"""
        self.update_status("Scanning website...")
        
        try:
            # Parse URL and custom name
            parts = url_entry.strip().split(None, 1)
            url = parts[0]
            custom_name = parts[1] if len(parts) > 1 else None
            
            # Check if it's a sitemap
            if 'sitemap' in url.lower() or url.endswith('.xml'):
                self.log(f"Scanning sitemap: {url}")
                result = self.sitemap_scanner.scan_sitemap(url, progress_callback=self.log)
                
                # Show results
                msg = f"Sitemap Scan Results:\n\n"
                msg += f"Total URLs: {result['total_count']}\n"
                msg += f"Page URLs: {len(result['page_urls'])}\n"
                msg += f"Image URLs: {len(result['image_urls'])}\n"
                msg += f"Video URLs: {len(result['video_urls'])}\n\n"
                
                if custom_name:
                    msg += f"Will save to: Downloads/{custom_name}/\n\n"
                
                msg += "Click 'Scrape All' to download media from these URLs"
                
                self.root.after(0, lambda: messagebox.showinfo("Scan Complete", msg))
                self.log(f"Scan complete: {result['total_count']} URLs found")
            else:
                self.log(f"Scanning URL: {url}")
                result = self.sitemap_scanner.scan_url(url, progress_callback=self.log)
                
                total_media = len(result['images']) + len(result['videos']) + len(result['links'])
                
                # Show results
                msg = f"URL Scan Results:\n\n"
                msg += f"⚠️ PREVIEW ONLY (no JavaScript/scrolling)\n"
                msg += f"Images: {len(result['images'])}\n"
                msg += f"Videos: {len(result['videos'])}\n"
                msg += f"Media Links: {len(result['links'])}\n"
                msg += f"Total: {total_media}\n\n"
                
                msg += "💡 Actual scraping will:\n"
                msg += "  • Render JavaScript with Playwright\n"
                msg += "  • Scroll 20 times to load all content\n"
                msg += "  • Find MUCH more media\n\n"
                
                if result['gallery_dl_supported']:
                    msg += "✓ gallery-dl supported\n"
                    msg += "Use 'Download with gallery-dl' button for best results\n"
                else:
                    msg += "Standard scraping available\n"
                
                if custom_name:
                    msg += f"\nWill save to: Downloads/{custom_name}/"
                
                msg += "\n\n👉 Click 'Scrape Active' to download with full rendering!"
                
                self.root.after(0, lambda: messagebox.showinfo("Scan Preview", msg))
                self.log(f"Scan preview: {total_media} media items found (without scrolling)")
            
            self.update_status("Scan complete")
        
        except Exception as e:
            self.log(f"Scan error: {str(e)}")
            self.update_status("Scan error")
    
    def download_with_gallerydl(self):
        """Download selected websites using gallery-dl"""
        # Check active list first
        selection = self.website_active_listbox.curselection()
        if selection:
            url_entry = self.website_active_listbox.get(selection[0])
        else:
            # Check inactive list
            selection = self.website_inactive_listbox.curselection()
            if selection:
                url_entry = self.website_inactive_listbox.get(selection[0])
            else:
                messagebox.showinfo("Info", "Please select a website to download")
                return
        
        if not self.gallery_dl.gallery_dl_available:
            response = messagebox.askyesno(
                "gallery-dl Not Found",
                "gallery-dl is not installed or not in PATH.\n\n"
                "Would you like to install it?\n\n"
                "Run: pip install gallery-dl"
            )
            if response:
                self.log("Please install gallery-dl: pip install gallery-dl")
            return
        
        thread = threading.Thread(target=self._download_gallerydl_thread, args=(url_entry,))
        thread.daemon = True
        thread.start()
    
    def _download_gallerydl_thread(self, url_entry):
        """Thread for downloading with gallery-dl"""
        self.is_downloading = True
        self.update_status("Downloading with gallery-dl...")
        
        try:
            # Parse URL and custom name
            parts = url_entry.strip().split(None, 1)
            url = parts[0]
            custom_name = parts[1] if len(parts) > 1 else None
            
            base_path = self.config.get('downloads.base_path', 'Downloads')
            
            # Determine folder name
            if custom_name:
                from .utils import sanitize_filename
                folder_name = sanitize_filename(custom_name)
            else:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace('www.', '')
                from .utils import sanitize_filename
                folder_name = sanitize_filename(domain)
            
            from .utils import ensure_download_directory
            download_path = ensure_download_directory(base_path, folder_name)
            
            self.log(f"Using gallery-dl to download: {url}")
            self.log(f"Saving to: {download_path}")
            
            downloaded = self.gallery_dl.download_url(url, download_path, progress_callback=self.log)
            
            self.log(f"gallery-dl downloaded {len(downloaded)} files")
            self.update_status("Download complete!")
        
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.update_status("Download error")
        
        finally:
            self.is_downloading = False
    
    # OnlyFans methods
    def launch_ofdl_exe(self):
        """Launch OF-DL.exe"""
        ofdl_path = self.ofdl_exe_path.get().strip()
        if not ofdl_path or not os.path.exists(ofdl_path):
            messagebox.showwarning("OF-DL Not Found", 
                "Please set the OF-DL.exe path first.\n\n" +
                "Click 'Download OF-DL' to get it, or 'Browse' to select existing installation.")
            return
        
        import subprocess
        self.log("=" * 60)
        self.log("LAUNCHING OF-DL")
        self.log("=" * 60)
        self.log(f"OF-DL Path: {ofdl_path}")
        self.update_status("OF-DL launched")
        
        try:
            # Launch OF-DL.exe in its own directory
            subprocess.Popen([ofdl_path], cwd=os.path.dirname(ofdl_path))
            self.log("✓ OF-DL opened successfully")
        except Exception as e:
            self.log(f"✗ Failed to launch OF-DL: {str(e)}")
            messagebox.showerror("Launch Error", f"Failed to launch OF-DL:\n{str(e)}")
    
    # OF-DL Integration Methods
    def browse_ofdl_exe(self):
        """Browse for OF-DL.exe"""
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            title="Select OF-DL.exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")]
        )
        if filename:
            self.ofdl_exe_path.delete(0, tk.END)
            self.ofdl_exe_path.insert(0, filename)
            self.config.set('onlyfans.ofdl_path', filename)
            self.log(f"OF-DL path set to: {filename}")
    
    def open_ofdl_download(self):
        """Open OF-DL download page"""
        import webbrowser
        webbrowser.open('https://git.ofdl.tools/sim0n00ps/OF-DL/releases')
        self.log("Opening OF-DL download page in browser...")
    
    def edit_ofdl_config(self):
        """Open OF-DL config.json in notepad"""
        ofdl_path = self.ofdl_exe_path.get().strip()
        if not ofdl_path or not os.path.exists(ofdl_path):
            messagebox.showwarning("OF-DL Not Found", "Please set the OF-DL.exe path first")
            return
        
        # config.json should be in same directory as OF-DL.exe
        config_path = os.path.join(os.path.dirname(ofdl_path), 'config.json')
        
        if not os.path.exists(config_path):
            # Create default config
            self._create_default_ofdl_config(config_path)
        
        # Open in notepad
        import subprocess
        subprocess.Popen(['notepad.exe', config_path])
        self.log(f"Opened config.json in notepad: {config_path}")
    
    def _create_default_ofdl_config(self, config_path):
        """Create default OF-DL config.json with GUI settings"""
        import json
        
        config = {
            "DownloadPath": str(self.config.get('downloads.base_path', 'Downloads')),
            "DownloadPosts": bool(self.config.get('onlyfans.download_posts', True)),
            "DownloadPaidPosts": bool(self.config.get('onlyfans.download_paid_posts', True)),
            "DownloadMessages": bool(self.config.get('onlyfans.download_messages', True)),
            "DownloadPaidMessages": bool(self.config.get('onlyfans.download_paid_messages', True)),
            "DownloadStories": bool(self.config.get('onlyfans.download_stories', True)),
            "DownloadHighlights": bool(self.config.get('onlyfans.download_highlights', True)),
            "DownloadArchived": bool(self.config.get('onlyfans.download_archived', True)),
            "DownloadStreams": bool(self.config.get('onlyfans.download_streams', True)),
            "DownloadImages": bool(self.config.get('onlyfans.download_images', True)),
            "DownloadVideos": bool(self.config.get('onlyfans.download_videos', True)),
            "DownloadAudios": bool(self.config.get('onlyfans.download_audios', True)),
            "DownloadAvatarHeaderPhoto": bool(self.config.get('onlyfans.download_avatar_header', True)),
            "FolderPerPost": bool(self.config.get('onlyfans.folder_per_post', False)),
            "FolderPerPaidPost": bool(self.config.get('onlyfans.folder_per_paid_post', False)),
            "FolderPerMessage": bool(self.config.get('onlyfans.folder_per_message', False)),
            "FolderPerPaidMessage": bool(self.config.get('onlyfans.folder_per_paid_message', False)),
            "SkipAds": bool(self.config.get('onlyfans.skip_ads', False)),
            "IgnoreOwnMessages": bool(self.config.get('onlyfans.ignore_own_messages', False)),
            "IncludeExpiredSubscriptions": bool(self.config.get('onlyfans.include_expired', False)),
            "IncludeRestrictedSubscriptions": bool(self.config.get('onlyfans.include_restricted', False)),
            "DownloadDuplicatedMedia": bool(self.config.get('onlyfans.download_duplicates', False)),
            "DownloadPostsIncrementally": bool(self.config.get('onlyfans.download_incrementally', False)),
            "NonInteractiveMode": False,
            "LoggingLevel": "Information"
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.log(f"Created default config.json: {config_path}")
    
    def _update_ofdl_config(self, config_path, custom_list=None, paid_only=False, expired_only=False):
        """Update OF-DL config.json with current GUI settings"""
        import json
        
        # Load existing config or create new
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # If expired_only mode, focus on expired/restricted subscriptions
        if expired_only:
            config["DownloadPath"] = str(self.config.get('downloads.base_path', 'Downloads'))
            config["DownloadPosts"] = True
            config["DownloadPaidPosts"] = True
            config["DownloadMessages"] = True
            config["DownloadPaidMessages"] = True
            config["DownloadStories"] = True  # Get everything while accounts still accessible
            config["DownloadHighlights"] = True
            config["DownloadArchived"] = True
            config["DownloadStreams"] = True
            config["DownloadImages"] = True
            config["DownloadVideos"] = True
            config["DownloadAudios"] = True
            config["DownloadAvatarHeaderPhoto"] = True
            config["FolderPerPost"] = bool(self.config.get('onlyfans.folder_per_post', False))
            config["FolderPerPaidPost"] = bool(self.config.get('onlyfans.folder_per_paid_post', False))
            config["FolderPerMessage"] = bool(self.config.get('onlyfans.folder_per_message', False))
            config["FolderPerPaidMessage"] = bool(self.config.get('onlyfans.folder_per_paid_message', False))
            config["SkipAds"] = True
            config["IgnoreOwnMessages"] = True
            config["IncludeExpiredSubscriptions"] = True  # KEY: Include expired
            config["IncludeRestrictedSubscriptions"] = True  # KEY: Include restricted/deleted
            config["DownloadDuplicatedMedia"] = False
            config["DownloadPostsIncrementally"] = False
            self.log("Config mode: EXPIRED/DELETED ACCOUNTS (includes expired + restricted)")
        # If paid_only mode, prioritize paid content
        elif paid_only:
            config["DownloadPath"] = str(self.config.get('downloads.base_path', 'Downloads'))
            config["DownloadPosts"] = False  # Skip free posts
            config["DownloadPaidPosts"] = True  # Download paid posts
            config["DownloadMessages"] = False  # Skip free messages
            config["DownloadPaidMessages"] = True  # Download paid messages
            config["DownloadStories"] = False
            config["DownloadHighlights"] = False
            config["DownloadArchived"] = True  # May contain paid content
            config["DownloadStreams"] = False
            config["DownloadImages"] = True
            config["DownloadVideos"] = True
            config["DownloadAudios"] = True
            config["DownloadAvatarHeaderPhoto"] = False
            config["FolderPerPost"] = bool(self.config.get('onlyfans.folder_per_post', False))
            config["FolderPerPaidPost"] = True  # Organize paid posts
            config["FolderPerMessage"] = bool(self.config.get('onlyfans.folder_per_message', False))
            config["FolderPerPaidMessage"] = True  # Organize paid messages
            config["SkipAds"] = True
            config["IgnoreOwnMessages"] = True
            config["IncludeExpiredSubscriptions"] = True  # Include expired to get all paid content
            config["IncludeRestrictedSubscriptions"] = True
            config["DownloadDuplicatedMedia"] = False
            config["DownloadPostsIncrementally"] = bool(self.config.get('onlyfans.download_incrementally', False))
            self.log("Config mode: PAID CONTENT ONLY (paid posts + paid messages)")
        else:
            # Normal mode: use GUI settings
            config["DownloadPath"] = str(self.config.get('downloads.base_path', 'Downloads'))
            config["DownloadPosts"] = bool(self.config.get('onlyfans.download_posts', True))
            config["DownloadPaidPosts"] = bool(self.config.get('onlyfans.download_paid_posts', True))
            config["DownloadMessages"] = bool(self.config.get('onlyfans.download_messages', True))
            config["DownloadPaidMessages"] = bool(self.config.get('onlyfans.download_paid_messages', True))
            config["DownloadStories"] = bool(self.config.get('onlyfans.download_stories', True))
            config["DownloadHighlights"] = bool(self.config.get('onlyfans.download_highlights', True))
            config["DownloadArchived"] = bool(self.config.get('onlyfans.download_archived', True))
            config["DownloadStreams"] = bool(self.config.get('onlyfans.download_streams', True))
            config["DownloadImages"] = bool(self.config.get('onlyfans.download_images', True))
            config["DownloadVideos"] = bool(self.config.get('onlyfans.download_videos', True))
            config["DownloadAudios"] = bool(self.config.get('onlyfans.download_audios', True))
            config["DownloadAvatarHeaderPhoto"] = bool(self.config.get('onlyfans.download_avatar_header', True))
            config["FolderPerPost"] = bool(self.config.get('onlyfans.folder_per_post', False))
            config["FolderPerPaidPost"] = bool(self.config.get('onlyfans.folder_per_paid_post', False))
            config["FolderPerMessage"] = bool(self.config.get('onlyfans.folder_per_message', False))
            config["FolderPerPaidMessage"] = bool(self.config.get('onlyfans.folder_per_paid_message', False))
            config["SkipAds"] = bool(self.config.get('onlyfans.skip_ads', False))
            config["IgnoreOwnMessages"] = bool(self.config.get('onlyfans.ignore_own_messages', False))
            config["IncludeExpiredSubscriptions"] = bool(self.config.get('onlyfans.include_expired', False))
            config["IncludeRestrictedSubscriptions"] = bool(self.config.get('onlyfans.include_restricted', False))
            config["DownloadDuplicatedMedia"] = bool(self.config.get('onlyfans.download_duplicates', False))
            config["DownloadPostsIncrementally"] = bool(self.config.get('onlyfans.download_incrementally', False))
        
        # Save
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.log(f"Updated OF-DL config: {config_path}")
    

    
    # Note: Direct OnlyFans API authentication methods removed.
    # The application now uses OF-DL (https://git.ofdl.tools/sim0n00ps/OF-DL) for all OnlyFans operations.
    # OF-DL handles authentication through its built-in browser, which is more reliable and avoids
    # OnlyFans' anti-bot detection that immediately logs out API-based authentication attempts.
    
    # UI update methods
    def update_status(self, message):
        """Update status bar"""
        self.status_var.set(message)
        self.root.update_idletasks()
    
    def start_progress(self, total):
        """Initialize progress bar for download operation"""
        self.total_items = total
        self.current_progress = 0
        self.progress_bar['maximum'] = total
        self.progress_bar['value'] = 0
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)
        self.update_progress_status()
    
    def update_progress(self, current=None):
        """Update progress bar and status text"""
        if current is not None:
            self.current_progress = current
        else:
            self.current_progress += 1
        
        self.progress_bar['value'] = self.current_progress
        self.update_progress_status()
    
    def update_progress_status(self):
        """Update status text with progress"""
        if self.total_items > 0:
            percentage = (self.current_progress / self.total_items) * 100
            self.status_var.set(f"Downloading {self.current_progress}/{self.total_items} ({percentage:.1f}%)")
        self.root.update_idletasks()
    
    def end_progress(self):
        """Hide progress bar after completion"""
        self.progress_bar.pack_forget()
        self.current_progress = 0
        self.total_items = 0

    # Duplicates tab progress helpers
    def _dup_progress_start(self, total: int):
        try:
            if total and hasattr(self, 'dup_progress_bar'):
                self.dup_progress_bar['maximum'] = max(1, total)
                self.dup_progress_bar['value'] = 0
                self.dup_progress_bar.pack(fill='x', pady=(6,0))
                if hasattr(self, 'dup_progress_var'):
                    self.dup_progress_var.set(f"Preparing... 0/{total} (0%)")
            # Mirror to global status bar progress
            if total:
                self.start_progress(total)
                self.status_var.set("Scanning duplicates...")
                try:
                    self.root.title(f"Media Scraper Bot – 0%")
                except Exception:
                    pass
            # Mini progress window
            self._mini_progress_show(total)
        except Exception:
            pass

    def _dup_progress_update(self, current: int, total: int):
        try:
            if hasattr(self, 'dup_progress_bar'):
                self.dup_progress_bar['value'] = min(current, max(1, total))
                pct = (current / total * 100) if total else 0
                if hasattr(self, 'dup_progress_var'):
                    self.dup_progress_var.set(f"Scanning {current}/{total} ({pct:.1f}%)")
            # Mirror to global status bar
            if total:
                self.progress_bar['maximum'] = max(1, total)
                self.progress_bar['value'] = min(current, total)
                self.status_var.set(f"Scanning {current}/{total} ({pct:.1f}%)")
                try:
                    self.root.title(f"Media Scraper Bot – {pct:.0f}%")
                except Exception:
                    pass
            # Mini progress window update
            self._mini_progress_update(current, total)
        except Exception:
            pass

    def _dup_progress_finish(self):
        try:
            if hasattr(self, 'dup_progress_var'):
                self.dup_progress_var.set("Done")
            if hasattr(self, 'dup_progress_bar'):
                self.dup_progress_bar.pack_forget()
            # Reset global status bar and window title
            self.end_progress()
            try:
                self.root.title("Media Scraper Bot")
            except Exception:
                pass
            self._mini_progress_finish()
        except Exception:
            pass

    # Mini progress window (always-on-top) for long duplicate scans
    def _mini_progress_show(self, total: int):
        try:
            # reset flags
            self.dup_pause_flag = False
            self.dup_cancel_flag = False
            # create window
            self.mini_prog_win = tk.Toplevel(self.root)
            self.mini_prog_win.title("Scanning… 0%")
            self.mini_prog_win.attributes('-topmost', True)
            self.mini_prog_win.resizable(False, False)
            self.mini_prog_win.geometry("320x110+80+80")
            self.mini_prog_win.protocol("WM_DELETE_WINDOW", self._cancel_dup_run)
            frm = ttk.Frame(self.mini_prog_win, padding=8)
            frm.pack(fill='both', expand=True)
            self.mini_prog_var = tk.StringVar(value="Preparing…")
            ttk.Label(frm, textvariable=self.mini_prog_var).pack(anchor='w')
            self.mini_prog_bar = ttk.Progressbar(frm, mode='determinate', maximum=max(1, total))
            self.mini_prog_bar.pack(fill='x', pady=(6,8))
            btns = ttk.Frame(frm)
            btns.pack(fill='x')
            self.mini_pause_btn = ttk.Button(btns, text="Pause", command=self._toggle_pause_dup_run, width=12)
            self.mini_pause_btn.pack(side=tk.LEFT)
            ttk.Button(btns, text="Cancel", command=self._cancel_dup_run, width=12).pack(side=tk.RIGHT)
        except Exception:
            pass

    def _mini_progress_update(self, current: int, total: int):
        try:
            if hasattr(self, 'mini_prog_bar') and self.mini_prog_bar:
                self.mini_prog_bar['maximum'] = max(1, total)
                self.mini_prog_bar['value'] = min(current, total)
                pct = (current / total * 100) if total else 0
                if hasattr(self, 'mini_prog_var') and self.mini_prog_var:
                    self.mini_prog_var.set(f"Scanning {current}/{total} ({pct:.1f}%)")
                if hasattr(self, 'mini_prog_win') and self.mini_prog_win:
                    try:
                        self.mini_prog_win.title(f"Scanning… {pct:.0f}%")
                    except Exception:
                        pass
        except Exception:
            pass

    def _mini_progress_finish(self):
        try:
            if hasattr(self, 'mini_prog_win') and self.mini_prog_win:
                self.mini_prog_win.destroy()
                self.mini_prog_win = None
        except Exception:
            pass

    def _toggle_pause_dup_run(self):
        try:
            self.dup_pause_flag = not getattr(self, 'dup_pause_flag', False)
            if hasattr(self, 'mini_pause_btn') and self.mini_pause_btn:
                self.mini_pause_btn.configure(text="Resume" if self.dup_pause_flag else "Pause")
            self.log("Paused" if self.dup_pause_flag else "Resumed")
        except Exception:
            pass

    def _cancel_dup_run(self):
        try:
            self.dup_cancel_flag = True
            self.log("Cancel requested")
            if hasattr(self, 'mini_prog_win') and self.mini_prog_win:
                self.mini_prog_win.title("Cancelling…")
        except Exception:
            pass

    # Toggle maximize of Duplicates tab log section
    def toggle_dup_log_maximize(self):
        try:
            self.dup_log_max = not getattr(self, 'dup_log_max', False)
            frames = [
                getattr(self, 'dup_info_frame', None),
                getattr(self, 'dup_quick_frame', None),
                getattr(self, 'dup_filters_frame', None),
                getattr(self, 'dup_manage_frame', None),
                getattr(self, 'dup_stats_frame', None),
                getattr(self, 'dup_prog_frame', None),
            ]
            if self.dup_log_max:
                # Hide all but progress+log; expand log
                for f in frames:
                    try:
                        if f: f.pack_forget()
                    except Exception:
                        pass
                try:
                    self.dup_log_frame.pack_forget()
                    self.dup_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
                except Exception:
                    pass
            else:
                # Restore layout by repacking frames in order
                try:
                    if self.dup_info_frame: self.dup_info_frame.pack(fill='x', padx=10, pady=5)
                    if self.dup_quick_frame: self.dup_quick_frame.pack(fill='x', padx=10, pady=5)
                    if self.dup_filters_frame: self.dup_filters_frame.pack(fill='x', padx=10, pady=5)
                    if self.dup_manage_frame: self.dup_manage_frame.pack(fill='x', padx=10, pady=5)
                    if self.dup_stats_frame: self.dup_stats_frame.pack(fill='x', padx=10, pady=5)
                    if self.dup_prog_frame: self.dup_prog_frame.pack(fill='x', padx=10, pady=5)
                    self.dup_log_frame.pack_forget()
                    self.dup_log_frame.pack(fill='both', expand=True, padx=10, pady=5)
                except Exception:
                    pass
        except Exception:
            pass
    
    def log(self, message):
        """Add message to log"""
        # Main log (Settings tab)
        try:
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.see(tk.END)
        except Exception:
            pass
        # Duplicates tab log (if present)
        if hasattr(self, 'dup_log_text'):
            try:
                self.dup_log_text.insert(tk.END, message + '\n')
                self.dup_log_text.see(tk.END)
            except Exception:
                pass
        # Floating log window (if open)
        if hasattr(self, 'floating_log_text') and self.floating_log_text:
            try:
                self.floating_log_text.insert(tk.END, message + '\n')
                if not getattr(self, 'floating_log_paused', False):
                    self.floating_log_text.see(tk.END)
            except Exception:
                pass
        self.root.update_idletasks()

    # Floating log window for visibility when main window is minimized
    def open_floating_log(self):
        try:
            if hasattr(self, 'floating_log_win') and self.floating_log_win:
                try:
                    self.floating_log_win.deiconify()
                    self.floating_log_win.lift()
                    return
                except Exception:
                    pass
            self.floating_log_win = tk.Toplevel(self.root)
            self.floating_log_win.title("Activity Log")
            self.floating_log_win.geometry("720x420+100+100")
            self.floating_log_win.attributes('-topmost', True)
            # Allow independent visibility
            try:
                self.floating_log_win.wm_attributes('-toolwindow', True)
            except Exception:
                pass
            frm = ttk.Frame(self.floating_log_win, padding=6)
            frm.pack(fill='both', expand=True)
            header = ttk.Frame(frm)
            header.pack(fill='x', pady=(0,6))
            self.floating_topmost_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(header, text="Always on top", variable=self.floating_topmost_var,
                            command=lambda: self.floating_log_win.attributes('-topmost', bool(self.floating_topmost_var.get()))).pack(side=tk.LEFT)
            self.floating_log_paused = False
            def toggle_autoscroll():
                self.floating_log_paused = not self.floating_log_paused
                auto_btn.configure(text=("Resume autoscroll" if self.floating_log_paused else "Pause autoscroll"))
            auto_btn = ttk.Button(header, text="Pause autoscroll", command=toggle_autoscroll)
            auto_btn.pack(side=tk.LEFT, padx=8)
            ttk.Button(header, text="Clear", command=lambda: self.floating_log_text.delete('1.0', tk.END)).pack(side=tk.LEFT)
            body = ttk.Frame(frm)
            body.pack(fill='both', expand=True)
            self.floating_log_text = tk.Text(body, wrap='word')
            fl_scroll = ttk.Scrollbar(body, orient='vertical', command=self.floating_log_text.yview)
            self.floating_log_text.configure(yscrollcommand=fl_scroll.set)
            self.floating_log_text.pack(side=tk.LEFT, fill='both', expand=True)
            fl_scroll.pack(side=tk.RIGHT, fill='y')
        except Exception:
            pass
    
    # History management methods
    def show_history_stats(self):
        """Show download history statistics"""
        history_stats = self.download_history.get_statistics()
        file_stats = self.duplicate_checker.get_statistics()
        
        msg = "Download History Statistics:\n\n"
        msg += f"Reddit:\n"
        msg += f"  - {history_stats['total_reddit_sources']} sources tracked\n"
        msg += f"  - {history_stats['total_reddit_posts']} posts seen\n\n"
        msg += f"Twitter:\n"
        msg += f"  - {history_stats['total_twitter_sources']} users tracked\n"
        msg += f"  - {history_stats['total_twitter_tweets']} tweets seen\n\n"
        msg += f"Websites:\n"
        msg += f"  - {history_stats['total_websites']} websites tracked\n"
        msg += f"  - {history_stats['total_website_urls']} URLs seen\n\n"
        
        msg += "="*40 + "\n\n"
        msg += f"Downloaded Files:\n"
        msg += f"  - {file_stats['video_count']} videos\n"
        msg += f"  - {file_stats['image_count']} images\n"
        msg += f"  - {file_stats['other_count']} other files\n"
        msg += f"  - {file_stats['total_files']} total files\n\n"
        msg += f"Total Size: {file_stats['total_size_gb']:.2f} GB ({file_stats['total_size_mb']:.2f} MB)\n"
        
        messagebox.showinfo("Download History Statistics", msg)
        self.log("Displayed history statistics")
    
    def clear_all_history(self):
        """Clear all download history after confirmation"""
        response = messagebox.askyesno(
            "Clear History",
            "Are you sure you want to clear all download history?\n\n"
            "This will cause the scraper to re-download all content on the next run."
        )
        
        if response:
            self.download_history.clear_all_history()
            messagebox.showinfo("Success", "Download history cleared")
            self.log("Cleared all download history")
    
    # Folder organization
    def flatten_folder_structure(self):
        """Flatten nested folder structures - move all files to Downloads\\username\\ level"""
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        
        # Let user choose the root folder (e.g., Downloads\OnlyFans)
        from tkinter import filedialog
        root_dir = filedialog.askdirectory(
            title="Select root folder (e.g., Downloads\\OnlyFans) - will flatten each username subfolder",
            initialdir=base_path
        )
        
        if not root_dir:
            return
        
        # Find all immediate subdirectories (usernames)
        try:
            subdirs = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
        except Exception as e:
            messagebox.showerror("Error", f"Cannot read directory:\n\n{e}")
            return
        
        if not subdirs:
            messagebox.showinfo("No Folders", f"No subfolders found in:\n{root_dir}")
            return
        
        # Confirm action
        response = messagebox.askyesno(
            "Flatten Folder Structure",
            f"This will flatten {len(subdirs)} user folders:\n\n" +
            f"Root: {root_dir}\n" +
            f"Users: {', '.join(subdirs[:5])}{' ...' if len(subdirs) > 5 else ''}\n\n" +
            "Each username folder will be flattened separately:\n" +
            "  Downloads\\OnlyFans\\username\\posts\\file.jpg\n" +
            "  → Downloads\\OnlyFans\\username\\file.jpg\n\n" +
            "Files stay separated by username.\n\n" +
            "Continue?"
        )
        
        if not response:
            return
        
        thread = threading.Thread(target=self._flatten_all_users_thread, args=(root_dir, subdirs))
        thread.daemon = True
        thread.start()
    
    def _flatten_all_users_thread(self, root_dir, subdirs):
        """Thread to flatten all user folders in root directory"""
        self.is_downloading = True
        self.update_status("Flattening folder structures...")
        self.log("=" * 60)
        self.log(f"FLATTENING FOLDER STRUCTURES IN: {root_dir}")
        self.log(f"Processing {len(subdirs)} user folders")
        self.log("=" * 60)
        
        total_moved = 0
        total_removed = 0
        total_errors = 0
        
        for idx, username in enumerate(subdirs, 1):
            user_dir = os.path.join(root_dir, username)
            self.log(f"\n[{idx}/{len(subdirs)}] Processing: {username}")
            self.update_status(f"Flattening {username} ({idx}/{len(subdirs)})...")
            
            try:
                moved, removed, errors = self._flatten_single_folder(user_dir)
                total_moved += moved
                total_removed += removed
                total_errors += errors
                self.log(f"  ✓ {username}: {moved} files moved, {removed} empty folders removed")
            except Exception as e:
                self.log(f"  ✗ {username}: Error - {e}")
                total_errors += 1
        
        self.log("=" * 60)
        self.log(f"✅ ALL FOLDERS FLATTENED!")
        self.log(f"Total files moved: {total_moved}")
        self.log(f"Total empty folders removed: {total_removed}")
        if total_errors > 0:
            self.log(f"Total errors: {total_errors}")
        self.log("=" * 60)
        
        self.update_status("Folder flattening complete")
        self.root.after(0, lambda: messagebox.showinfo("Complete", 
            f"All folders flattened!\n\n" +
            f"Users processed: {len(subdirs)}\n" +
            f"Files moved: {total_moved}\n" +
            f"Empty folders removed: {total_removed}\n" +
            f"Errors: {total_errors}"))
        
        self.is_downloading = False
    
    def _flatten_single_folder(self, root_dir):
        """Flatten a single folder structure and return counts (moved, removed_dirs, errors)"""
        moved_count = 0
        error_count = 0
        
        # Walk through all subdirectories
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
            # Skip the root directory itself
            if dirpath == root_dir:
                continue
            
            for filename in filenames:
                source_path = os.path.join(dirpath, filename)
                dest_path = os.path.join(root_dir, filename)
                
                try:
                    # If file already exists in root, handle conflict
                    if os.path.exists(dest_path):
                        # Check if they're the same file
                        if os.path.samefile(source_path, dest_path):
                            continue
                        
                        # Handle naming conflict - add number suffix
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(dest_path):
                            dest_path = os.path.join(root_dir, f"{base}_{counter}{ext}")
                            counter += 1
                    
                    # Move file to root
                    import shutil
                    shutil.move(source_path, dest_path)
                    moved_count += 1
                
                except Exception as e:
                    error_count += 1
        
        # Remove empty directories (call multiple times to catch nested empties)
        self.log(f"  Removing empty folders from: {root_dir}")
        empty_dirs_removed = 0
        for _ in range(3):  # Run multiple passes to catch nested empty folders
            removed = self._delete_empty_folders(root_dir)
            empty_dirs_removed += removed
            if removed == 0:
                break
        
        return moved_count, empty_dirs_removed, error_count
    
    # Duplicate detection and migration
    def scan_existing_files(self):
        """Scan existing Downloads folder and add files to hash database"""
        if self.is_downloading:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        if not os.path.exists(base_path):
            messagebox.showinfo("Info", f"Downloads folder not found: {base_path}")
            return
        
        response = messagebox.askyesno(
            "Scan Existing Files",
            f"This will scan all files in '{base_path}' and add them to the duplicate detection database.\n\n"
            "This may take a while for large collections.\n\nContinue?"
        )
        
        if response:
            thread = threading.Thread(target=self._scan_existing_files_thread, args=(base_path,))
            thread.daemon = True
            thread.start()
    
    def _scan_existing_files_thread(self, directory):
        """Thread for scanning existing files"""
        self.is_downloading = True
        self.update_status("Scanning existing files...")
        self.log(f"Starting scan of {directory}...")
        
        try:
            files_added = self.duplicate_checker.scan_existing_files(directory, progress_callback=self.log)
            self.update_status("Scan complete!")
            self.log(f"Scan complete! Added {files_added} files to duplicate detection database.")
            messagebox.showinfo("Scan Complete", f"Added {files_added} files to duplicate detection database.")
        except Exception as e:
            self.log(f"Error scanning files: {str(e)}")
            self.update_status("Scan error")
        finally:
            self.is_downloading = False
    
    def scan_and_move_duplicates(self):
        """Advanced: Choose source drive to scan, find duplicates (including matches
        against tracked database), then choose where to move them."""
        if self.is_downloading:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        
        # Step 1: Choose source drive/folder
        source_dir = filedialog.askdirectory(title="Step 1: Choose source folder/drive to scan for duplicates")
        if not source_dir:
            return
        
        # Step 2: Choose destination for duplicates
        dest_dir = filedialog.askdirectory(title="Step 2: Choose destination folder for duplicate files")
        if not dest_dir:
            return
        
        self.log(f"Advanced scan: Source={source_dir}, Destination={dest_dir}")
        
        def _worker():
            try:
                # Phase 1: group by file size
                size_map = {}
                for r, dnames, fnames in os.walk(source_dir):
                    for fn in fnames:
                        fp = os.path.join(r, fn)
                        try:
                            size = os.path.getsize(fp)
                        except Exception:
                            continue
                        size_map.setdefault(size, []).append(fp)
                
                # Phase 2: hash files and build source hash groups
                source_hash_groups = {}
                for size, paths in size_map.items():
                    # Hash all files for this size bucket (even if only one) so we can
                    # also detect duplicates against the tracked database.
                    for fp in paths:
                        h = self.duplicate_checker.calculate_file_hash(fp)
                        if not h:
                            continue
                        source_hash_groups.setdefault(h, []).append(fp)

                # Phase 3: merge with tracked database so duplicates across locations are found
                duplicates = {}
                for h, src_paths in source_hash_groups.items():
                    paths = list(src_paths)
                    tracked_info = self.duplicate_checker.file_hashes.get(h)
                    tracked_path = None
                    if isinstance(tracked_info, dict):
                        tracked_path = tracked_info.get('path')
                        if tracked_path and os.path.exists(tracked_path) and tracked_path not in paths:
                            # Put tracked path first so it becomes the keeper; source files will be selected to move
                            paths = [tracked_path] + paths
                    # Only create a duplicate group if there are at least 2 files total
                    if len(paths) > 1:
                        duplicates[h] = paths
                
                # Phase 4: Show dialog with pre-set destination
                self.root.after(0, lambda: self._show_duplicate_dialog_with_destination(
                    duplicates, source_dir, dest_dir))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Scan Error", str(e)))
        
        t = threading.Thread(target=_worker)
        t.daemon = True
        t.start()
    
    def scan_drive_for_duplicates(self):
        """Choose a folder/drive and scan for duplicate files with selection dialog."""
        if self.is_downloading:
            messagebox.showwarning("Warning", "Please wait for current operation to complete")
            return
        root_dir = filedialog.askdirectory(title="Choose folder/drive to scan")
        if not root_dir:
            return
        self.log(f"Scanning for duplicates under: {root_dir}")

        def _worker():
            try:
                # Phase 1: group by file size to reduce hashing
                size_map = {}
                for r, dnames, fnames in os.walk(root_dir):
                    for fn in fnames:
                        fp = os.path.join(r, fn)
                        try:
                            size = os.path.getsize(fp)
                        except Exception:
                            continue
                        size_map.setdefault(size, []).append(fp)
                # Phase 2: hash only files with same size
                duplicates = {}
                for size, paths in size_map.items():
                    if len(paths) < 2:
                        continue
                    hash_groups = {}
                    for fp in paths:
                        h = self.duplicate_checker.calculate_file_hash(fp)
                        if not h:
                            continue
                        hash_groups.setdefault(h, []).append(fp)
                    for h, files in hash_groups.items():
                        if len(files) > 1:
                            duplicates[h] = files
                self.root.after(0, lambda: self._show_duplicate_dialog(duplicates, root_for_cleanup=root_dir))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Scan Error", str(e)))
        t = threading.Thread(target=_worker)
        t.daemon = True
        t.start()

    def _run_preserve_duplicates(self, source_dir: str, dest_dir: str):
        """Generic runner: scan source, move duplicates to dest preserving structure, clean empty folders.
        Now merges with global hash DB to detect cross-folder duplicates.
        Honors filter settings from the Filters section."""
        if self.is_downloading:
            messagebox.showwarning("Busy", "Please wait for current operation to complete")
            return

        # snapshot filters so the worker uses a consistent view
        filters = self._get_filters()

        self.is_downloading = True
        self.update_status(f"Scanning {source_dir} for duplicates...")
        self.log(f"Run: scanning {source_dir} and moving duplicates to {dest_dir} (preserve structure + global DB)")

        def _worker():
            import shutil
            try:
                dest_abs = os.path.abspath(dest_dir).lower()
                source_abs = os.path.abspath(source_dir)
                # Phase 0: pre-count eligible files for progress
                self.log("📊 Phase 1/3: Counting eligible files...")
                total_candidates = 0
                folders_counted = 0
                import time
                count_start = time.time()
                for r, dnames, fnames in os.walk(source_abs):
                    dnames[:] = [d for d in dnames
                                 if os.path.abspath(os.path.join(r, d)).lower() != dest_abs
                                 and not any(tok in os.path.abspath(os.path.join(r, d)).lower() for tok in filters['exclude_tokens'])]
                    folders_counted += 1
                    if folders_counted % 100 == 0:
                        self.log(f"  Counting... {folders_counted} folders checked, {total_candidates} files found")
                    for fn in fnames:
                        fp = os.path.join(r, fn)
                        abspath_lower = os.path.abspath(fp).lower()
                        if abspath_lower.startswith(dest_abs):
                            continue
                        if any(tok in abspath_lower for tok in filters['exclude_tokens']):
                            continue
                        ext = os.path.splitext(fp)[1].lower()
                        if filters['include_exts'] and ext not in filters['include_exts']:
                            continue
                        try:
                            if os.path.getsize(fp) < filters['min_size_bytes']:
                                continue
                        except Exception:
                            continue
                        if filters['ignore_hidden_system'] and self._is_hidden_or_system_win(fp):
                            continue
                        total_candidates += 1
                count_elapsed = time.time() - count_start
                self.log(f"✓ Found {total_candidates} eligible files in {folders_counted} folders ({count_elapsed:.1f}s)")

                # Prime the duplicates progress bar in UI thread
                self.root.after(0, lambda: self._dup_progress_start(total_candidates))

                # Phase 1: hash all files under source (excluding dest_dir)
                self.log("🔍 Phase 2/3: Scanning and hashing files...")
                hash_groups = {}
                folders_scanned = 0
                files_hashed = 0
                files_skipped = 0
                canceled = False
                hash_start = time.time()
                last_log_time = hash_start
                for r, dnames, fnames in os.walk(source_abs):
                    # prune destination folder to avoid scanning it
                    dnames[:] = [d for d in dnames
                                 if os.path.abspath(os.path.join(r, d)).lower() != dest_abs
                                 and not any(tok in os.path.abspath(os.path.join(r, d)).lower() for tok in filters['exclude_tokens'])]
                    folders_scanned += 1
                    current_time = time.time()
                    # Log every 3 seconds or every 100 folders
                    if current_time - last_log_time >= 3.0 or folders_scanned % 100 == 0:
                        elapsed = current_time - hash_start
                        rate = files_hashed / elapsed if elapsed > 0 else 0
                        rel_folder = os.path.relpath(r, source_abs)
                        if len(rel_folder) > 60:
                            rel_folder = rel_folder[:57] + "..."
                        self.log(f"  📁 {rel_folder}")
                        self.log(f"     {files_hashed}/{total_candidates} hashed ({rate:.1f} files/sec) | {folders_scanned} folders")
                        last_log_time = current_time
                    for fn in fnames:
                        # cancel/pause checks
                        if getattr(self, 'dup_cancel_flag', False):
                            canceled = True
                            break
                        while getattr(self, 'dup_pause_flag', False):
                            time.sleep(0.2)
                        fp = os.path.join(r, fn)
                        try:
                            # skip any files inside dest (extra safety)
                            if os.path.abspath(fp).lower().startswith(dest_abs):
                                continue
                            abspath_lower = os.path.abspath(fp).lower()
                            if any(tok in abspath_lower for tok in filters['exclude_tokens']):
                                continue
                            # type filter
                            ext = os.path.splitext(fp)[1].lower()
                            if filters['include_exts'] and ext not in filters['include_exts']:
                                continue
                            # size filter
                            try:
                                if os.path.getsize(fp) < filters['min_size_bytes']:
                                    continue
                            except Exception:
                                continue
                            # hidden/system
                            if filters['ignore_hidden_system'] and self._is_hidden_or_system_win(fp):
                                continue
                            h = self.duplicate_checker.calculate_file_hash(fp)
                        except Exception:
                            h = None
                        if not h:
                            continue
                        hash_groups.setdefault(h, []).append(fp)
                        files_hashed += 1
                        # update progress
                        if total_candidates:
                            curr = files_hashed if files_hashed <= total_candidates else total_candidates
                            self.root.after(0, lambda c=curr, t=total_candidates: self._dup_progress_update(c, t))

                hash_elapsed = time.time() - hash_start
                avg_rate = files_hashed / hash_elapsed if hash_elapsed > 0 else 0
                self.log(f"✓ Hashing complete: {files_hashed} files in {folders_scanned} folders ({hash_elapsed:.1f}s, avg {avg_rate:.1f} files/sec)")
                
                if canceled:
                    self.log("❌ Scan canceled by user")
                    self.root.after(0, lambda: self._dup_progress_finish())
                    return
                
                # Phase 3: merge with global DB and determine moves
                self.log("🔎 Phase 3/3: Detecting duplicates (including global DB matches)...")
                self.log(f"  Analyzing {len(hash_groups)} unique file signatures...")
                self.log(f"  Global DB contains {len(self.duplicate_checker.file_hashes)} tracked files")
                
                to_move = []
                dup_groups = 0
                cross_folder_matches = 0
                
                for h, paths in hash_groups.items():
                    # Check if this hash exists in global DB outside source
                    tracked_info = self.duplicate_checker.file_hashes.get(h)
                    keeper_path = None
                    
                    if tracked_info and isinstance(tracked_info, dict):
                        tracked_path = tracked_info.get('path')
                        if tracked_path and os.path.exists(tracked_path):
                            tracked_abs = os.path.abspath(tracked_path)
                            # If tracked file is outside source tree, it's a cross-folder duplicate
                            if not tracked_abs.startswith(source_abs):
                                keeper_path = tracked_path
                                cross_folder_matches += 1
                    
                    # Build final path list: [keeper, ...duplicates]
                    final_paths = list(paths)
                    if keeper_path:
                        # All files in source are duplicates of the external keeper
                        for p in final_paths:
                            rel = os.path.relpath(p, start=source_abs)
                            dest_path = os.path.join(dest_dir, rel)
                            to_move.append((p, dest_path))
                        dup_groups += 1
                    elif len(final_paths) > 1:
                        # Internal duplicates within source (keep first)
                        dup_groups += 1
                        for p in final_paths[1:]:
                            rel = os.path.relpath(p, start=source_abs)
                            dest_path = os.path.join(dest_dir, rel)
                            to_move.append((p, dest_path))
                
                self.log(f"✓ Found {dup_groups} duplicate groups ({cross_folder_matches} cross-folder) with {len(to_move)} files to move")
                if len(to_move) == 0:
                    self.log("✓ No duplicates found! All files are unique.")
                    self.root.after(0, lambda: self._dup_progress_finish())
                    return
                
                self.log(f"📦 Moving {len(to_move)} duplicate files to {dest_dir}...")
                moved = 0
                failed = 0
                move_start = time.time()
                last_move_log = time.time()
                for idx, (src, dst) in enumerate(to_move, 1):
                    if getattr(self, 'dup_cancel_flag', False):
                        canceled = True
                        break
                    while getattr(self, 'dup_pause_flag', False):
                        time.sleep(0.2)
                    try:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        # handle collisions at destination
                        base, ext = os.path.splitext(os.path.basename(dst))
                        dst_dirname = os.path.dirname(dst)
                        candidate = dst
                        counter = 1
                        while os.path.exists(candidate):
                            candidate = os.path.join(dst_dirname, f"{base} ({counter}){ext}")
                            counter += 1
                        shutil.move(src, candidate)
                        try:
                            self.duplicate_checker.remove_file(src)
                            self.duplicate_checker.add_file(candidate)
                        except Exception:
                            pass
                        moved += 1
                        # Log every 3 seconds or every 25 files
                        current_move_time = time.time()
                        if current_move_time - last_move_log >= 3.0 or moved % 25 == 0:
                            pct = (idx / len(to_move)) * 100
                            rel_src = os.path.relpath(src, source_abs) if len(os.path.relpath(src, source_abs)) < 50 else os.path.relpath(src, source_abs)[:47] + "..."
                            self.log(f"  Moving {idx}/{len(to_move)} ({pct:.0f}%) - {rel_src}")
                            last_move_log = current_move_time
                    except Exception as e:
                        failed += 1
                        self.log(f"  ❌ Failed: {os.path.basename(src)}: {e}")

                # cleanup empty folders in source
                self.log("🧹 Cleaning up empty folders...")
                removed = self._delete_empty_folders(source_abs)
                if removed:
                    self.log(f"  ✓ Deleted {removed} empty folder(s) in source")
                else:
                    self.log(f"  ✓ No empty folders to clean")
                
                move_elapsed = time.time() - move_start
                total_elapsed = time.time() - count_start
                self.log("="*60)
                if canceled:
                    self.log("⚠️ OPERATION CANCELED BY USER")
                    self.log(f"  Partial results: {moved} files moved before cancellation")
                else:
                    self.log("✅ DUPLICATE SCAN COMPLETE")
                self.log(f"  Source: {source_dir}")
                self.log(f"  Destination: {dest_dir}")
                self.log(f"  Files scanned: {files_hashed} in {folders_scanned} folders")
                self.log(f"  Duplicate groups: {dup_groups if not canceled else '(partial)'}")
                self.log(f"  Files moved: {moved}")
                self.log(f"  Failed: {failed}")
                self.log(f"  Empty folders removed: {removed}")
                self.log(f"  Total time: {total_elapsed:.1f}s (count: {count_elapsed:.1f}s, hash: {hash_elapsed:.1f}s, move: {move_elapsed:.1f}s)")
                self.log("="*60)
                
                summary_msg = (
                    f"Visited {folders_scanned} folders\nHashed {files_hashed} files\n"
                    f"Moved {moved} file(s) to {dest_dir}\nFailed: {failed}\nRemoved empty folders: {removed}"
                )
                if canceled:
                    summary_msg = "⚠️ Operation cancelled by user\n\n" + summary_msg
                self.root.after(0, lambda m=summary_msg: messagebox.showinfo("Sweep Complete", m))
                self.root.after(0, self._dup_progress_finish)
            finally:
                self.is_downloading = False
                self.update_status("Idle")

    def _get_filters(self):
        """Build filter configuration from UI settings."""
        # groups
        images = {'.jpg','.jpeg','.png','.gif','.bmp','.webp','.tiff','.tif','.svg','.heic','.heif','.avif'}
        videos = {'.mp4','.webm','.mov','.avi','.mkv','.flv','.wmv','.m4v','.mpg','.mpeg','.3gp','.ts'}
        audio  = {'.mp3','.aac','.wav','.flac','.ogg','.m4a','.wma'}
        docs   = {'.pdf','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.txt','.rtf','.md'}
        archives = {'.zip','.rar','.7z','.tar','.gz','.bz2','.xz'}

        include = set()
        if getattr(self, 'filter_images', None) and self.filter_images.get():
            include |= images
        if getattr(self, 'filter_videos', None) and self.filter_videos.get():
            include |= videos
        if getattr(self, 'filter_audio', None) and self.filter_audio.get():
            include |= audio
        if getattr(self, 'filter_docs', None) and self.filter_docs.get():
            include |= docs
        if getattr(self, 'filter_archives', None) and self.filter_archives.get():
            include |= archives

        # custom extensions
        custom = []
        if getattr(self, 'filter_custom_exts', None):
            raw = self.filter_custom_exts.get()
            if raw:
                for part in raw.split(','):
                    p = part.strip().lower()
                    if not p:
                        continue
                    if not p.startswith('.'):
                        p = '.' + p
                    custom.append(p)
        include |= set(custom)

        # min size
        min_size_bytes = 0
        if getattr(self, 'filter_min_size_mb', None):
            try:
                min_size_bytes = int(float(self.filter_min_size_mb.get()) * 1024 * 1024)
            except Exception:
                min_size_bytes = 0

        # exclude tokens
        exclude_tokens = []
        if getattr(self, 'filter_exclude_paths', None):
            raw = self.filter_exclude_paths.get()
            if raw:
                exclude_tokens = [t.strip().lower() for t in raw.split(';') if t.strip()]

        ignore_hidden_system = False
        if getattr(self, 'filter_ignore_hidden_system', None):
            try:
                ignore_hidden_system = bool(self.filter_ignore_hidden_system.get())
            except Exception:
                ignore_hidden_system = False

        return {
            'include_exts': include,
            'min_size_bytes': min_size_bytes,
            'exclude_tokens': exclude_tokens,
            'ignore_hidden_system': ignore_hidden_system,
        }

    def _is_hidden_or_system_win(self, path: str) -> bool:
        """Return True if file is hidden or system on Windows; else False."""
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(ctypes.c_wchar_p(path))
            if attrs == -1:
                return False
            FILE_ATTRIBUTE_HIDDEN = 0x2
            FILE_ATTRIBUTE_SYSTEM = 0x4
            return bool(attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))
        except Exception:
            return False

    def run_drive_f_preserve_duplicates(self):
        """Quick run preset for F:\\ → F:\\duplicates preserving structure."""
        proceed = messagebox.askyesno(
            "Run Duplicate Sweep",
            "Scan all folders in F:\\ and move duplicates to F:\\duplicates,\n"
            "preserving folder structure and deleting empty folders?"
        )
        if not proceed:
            return
        self._run_preserve_duplicates("F:\\", os.path.join("F:\\", "duplicates"))

    def run_choose_preserve_duplicates(self):
        """Prompt for any source and destination, then run preserving structure and cleaning empties."""
        source_dir = filedialog.askdirectory(title="Choose source folder/drive to scan")
        if not source_dir:
            return
        default_dest = os.path.join(source_dir, "duplicates")
        dest_dir = filedialog.askdirectory(title="Choose destination folder for duplicates")
        if not dest_dir:
            return
        if os.path.abspath(dest_dir).lower() == os.path.abspath(source_dir).lower():
            messagebox.showwarning("Invalid Destination", "Destination must not be the same as the source folder.")
            return
        self._run_preserve_duplicates(source_dir, dest_dir)

    def refresh_drive_list(self):
        """Populate drive selection combobox with available Windows drives."""
        drives = []
        for code in range(ord('A'), ord('Z') + 1):
            letter = chr(code)
            root = f"{letter}:\\"
            try:
                if os.path.exists(root):
                    drives.append(root[:-1])  # store like 'C:'
            except Exception:
                pass
        self.drive_select_combo['values'] = drives
        if drives and not self.drive_select_var.get():
            self.drive_select_var.set(drives[0])

    def run_global_sweep(self):
        """One-click global sweep of entire Downloads folder for duplicates"""
        base_path = str(self.config.get('downloads.base_path', 'Downloads'))
        if not os.path.isdir(base_path):
            messagebox.showwarning("Invalid Path", f"Downloads folder not found: {base_path}")
            return
        
        dest_dir = os.path.join(base_path, "duplicates")
        proceed = messagebox.askyesno(
            "Global Duplicate Sweep",
            f"Scan entire Downloads folder:\n{base_path}\n\n"
            f"Move all duplicates to:\n{dest_dir}\n\n"
            "This will detect duplicates across all categories (reddit, twitter, websites, etc.) "
            "using the global hash database.\n\n"
            "Continue?"
        )
        if not proceed:
            return
        
        # Apply media filter preset if available
        if hasattr(self, 'include_media_var'):
            self._apply_media_filters(media=bool(self.include_media_var.get()))
        
        self._run_preserve_duplicates(base_path, dest_dir)
    
    def browse_dup_folder(self):
        """Browse for a folder to scan for duplicates"""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select folder to scan for duplicates")
        if folder:
            self.dup_folder_var.set(folder)
    
    def run_folder_duplicates(self):
        """Run duplicate scan on the specific folder selected"""
        folder = self.dup_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Invalid Folder", "Please select a valid folder to scan.")
            return
        dest_name = (self.drive_dest_var.get() or "duplicates").strip()
        if not dest_name:
            dest_name = "duplicates"
        dest_dir = os.path.join(folder, dest_name)
        proceed = messagebox.askyesno(
            "Run Duplicate Sweep",
            f"Scan {folder} and its subfolders for duplicates,\n"
            f"then move duplicates to {dest_dir},\n"
            "preserving folder structure and deleting empty folders?"
        )
        if not proceed:
            return
        # Apply media filter preset if checkbox exists
        if hasattr(self, 'include_media_var'):
            self._apply_media_filters(media=bool(self.include_media_var.get()))
        self._run_preserve_duplicates(folder, dest_dir)
    
    def run_selected_drive_preserve_duplicates(self):
        """Run preserving structure using the drive selected in the combobox and a destination name."""
        drive = self.drive_select_var.get()
        if not drive:
            messagebox.showwarning("No Drive Selected", "Please select a drive from the list.")
            return
        dest_name = (self.drive_dest_var.get() or "duplicates").strip()
        if not dest_name:
            dest_name = "duplicates"
        source_dir = f"{drive}\\"
        dest_dir = os.path.join(f"{drive}\\", dest_name)
        proceed = messagebox.askyesno(
            "Run Duplicate Sweep",
            f"Scan all folders in {source_dir} and move duplicates to {dest_dir},\n"
            "preserving folder structure and deleting empty folders?"
        )
        if not proceed:
            return
        # Apply simple media vs non-media preset if the checkbox exists
        if hasattr(self, 'include_media_var'):
            self._apply_media_filters(media=bool(self.include_media_var.get()))
        self._run_preserve_duplicates(source_dir, dest_dir)

    def _on_include_media_toggle(self):
        # Keep the filters UI in sync with the simple toggle
        try:
            self._apply_media_filters(media=bool(self.include_media_var.get()))
        except Exception:
            pass

    def _apply_media_filters(self, media: bool):
        """Apply filter presets: media=True selects Images+Videos+Audio, media=False selects Docs+Archives only."""
        try:
            if media:
                self.filter_images.set(True)
                self.filter_videos.set(True)
                self.filter_audio.set(True)
                self.filter_docs.set(False)
                self.filter_archives.set(False)
            else:
                self.filter_images.set(False)
                self.filter_videos.set(False)
                self.filter_audio.set(False)
                self.filter_docs.set(True)
                self.filter_archives.set(True)
            # Clear custom and keep min size as user set
            self.filter_custom_exts.set("")
        except Exception:
            # If filters not yet built, ignore
            pass

    def run_media_selected_drive_preserve_duplicates(self):
        self._apply_media_filters(media=True)
        self.run_selected_drive_preserve_duplicates()

    def run_nonmedia_selected_drive_preserve_duplicates(self):
        self._apply_media_filters(media=False)
        self.run_selected_drive_preserve_duplicates()

    
    def find_and_show_duplicates(self):
        """Find and display duplicate files with option to delete"""
        self.log("Searching for duplicate files...")
        duplicates = self.duplicate_checker.find_duplicates()
        return self._show_duplicate_dialog(duplicates)

    def _show_duplicate_dialog(self, duplicates, root_for_cleanup: str | None = None):
        if not duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate files found! All files are unique.")
            self.log("No duplicates found")
            return
        
        # Create a dialog window to show duplicates
        dialog = tk.Toplevel(self.root)
        dialog.title("Duplicate Files Found")
        dialog.geometry("900x650")
        
        # Info label
        info_frame = ttk.Frame(dialog, padding=10)
        info_frame.pack(fill='x')
        
        total_duplicates = sum(len(files) - 1 for files in duplicates.values())
        ttk.Label(info_frame, text=f"Found {len(duplicates)} groups of duplicates ({total_duplicates} duplicate files)", 
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text="Select files to delete (keeps first file in each group):", 
                 foreground="gray").pack(anchor='w', pady=(5, 0))
        
        # Option to delete empty folders after deletion
        delete_empty = tk.BooleanVar(value=True)
        ttk.Checkbutton(info_frame, text="Delete empty folders after deletion", variable=delete_empty).pack(anchor='w', pady=(6,0))
        
        # Scrollable frame for duplicates
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # Mouse wheel scrolling for the dialog
        def _on_mousewheel(event):
            try:
                delta = int(-1 * (event.delta / 120))
            except Exception:
                delta = -1
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        selected_files = []
        
        # Display each group of duplicates
        for idx, (file_hash, files) in enumerate(duplicates.items(), 1):
            group_frame = ttk.LabelFrame(scrollable, text=f"Duplicate Group {idx}", padding=10)
            group_frame.pack(fill='x', padx=10, pady=5)
            
            for i, file_path in enumerate(files):
                file_exists = os.path.exists(file_path)
                status = "✓" if file_exists else "✗ Missing"
                
                file_frame = ttk.Frame(group_frame)
                file_frame.pack(fill='x', pady=2)
                
                var = tk.BooleanVar(value=(i > 0 and file_exists))  # Auto-select all except first
                selected_files.append((var, file_path))
                
                cb = ttk.Checkbutton(file_frame, variable=var, 
                                    text=f"{status} {file_path}" if i > 0 else f"KEEP: {file_path}",
                                    state='normal' if i > 0 and file_exists else 'disabled')
                cb.pack(side=tk.LEFT, fill='x', expand=True)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Button frame
        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill='x', side='bottom')
        
        def delete_selected():
            to_delete = [path for var, path in selected_files if var.get()]
            if not to_delete:
                messagebox.showinfo("No Selection", "No files selected for deletion")
                return
            
            response = messagebox.askyesno(
                "Confirm Deletion",
                f"Delete {len(to_delete)} duplicate file(s)?\n\n"
                "This action cannot be undone!"
            )
            
            if response:
                deleted = 0
                failed = 0
                for file_path in to_delete:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            self.duplicate_checker.remove_file(file_path)
                            deleted += 1
                            self.log(f"Deleted duplicate: {file_path}")
                    except Exception as e:
                        failed += 1
                        self.log(f"Failed to delete {file_path}: {e}")
                
                # Optionally delete empty folders under root
                if root_for_cleanup and delete_empty.get():
                    removed = self._delete_empty_folders(root_for_cleanup)
                    if removed:
                        self.log(f"Deleted {removed} empty folder(s) under {root_for_cleanup}")
                
                messagebox.showinfo("Deletion Complete", 
                                   f"Deleted {deleted} file(s)\n"
                                   f"Failed: {failed}")
                dialog.destroy()
                self.log(f"Deleted {deleted} duplicate files")
        
        def move_selected():
            to_move = [path for var, path in selected_files if var.get()]
            if not to_move:
                messagebox.showinfo("No Selection", "No files selected to move")
                return
            
            dest_folder = filedialog.askdirectory(title=f"Choose destination for {len(to_move)} duplicate file(s)")
            if not dest_folder:
                return
            
            moved = 0
            failed = 0
            import shutil
            for file_path in to_move:
                try:
                    if os.path.exists(file_path):
                        fname = os.path.basename(file_path)
                        dest = os.path.join(dest_folder, fname)
                        # Handle name collisions
                        base, ext = os.path.splitext(fname)
                        counter = 1
                        while os.path.exists(dest):
                            dest = os.path.join(dest_folder, f"{base} ({counter}){ext}")
                            counter += 1
                        shutil.move(file_path, dest)
                        # Update duplicate tracker
                        try:
                            self.duplicate_checker.remove_file(file_path)
                            self.duplicate_checker.add_file(dest)
                        except Exception:
                            pass
                        moved += 1
                        self.log(f"Moved duplicate: {file_path} → {dest}")
                except Exception as e:
                    failed += 1
                    self.log(f"Failed to move {file_path}: {e}")
            
            # Optionally delete empty folders under root
            if root_for_cleanup and delete_empty.get():
                removed = self._delete_empty_folders(root_for_cleanup)
                if removed:
                    self.log(f"Deleted {removed} empty folder(s) under {root_for_cleanup}")
            
            messagebox.showinfo("Move Complete", 
                               f"Moved {moved} file(s)\n"
                               f"Failed: {failed}")
            dialog.destroy()
            self.log(f"Moved {moved} duplicate files to {dest_folder}")
        
        ttk.Button(btn_frame, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Move Selected To...", command=move_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        self.log(f"Found {len(duplicates)} groups of duplicates")

    def _show_duplicate_dialog_with_destination(self, duplicates, source_dir: str, dest_dir: str):
        """Show duplicates with pre-configured destination for moving."""
        if not duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate files found! All files are unique.")
            self.log("No duplicates found")
            return
        
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Duplicates Found - Auto-Move to {dest_dir}")
        dialog.geometry("900x650")
        
        # Info header
        info_frame = ttk.Frame(dialog, padding=10)
        info_frame.pack(fill='x')
        
        total_duplicates = sum(len(files) - 1 for files in duplicates.values())
        ttk.Label(info_frame, text=f"Found {len(duplicates)} groups ({total_duplicates} duplicates)", 
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        ttk.Label(info_frame, text=f"Source: {source_dir}", foreground="gray").pack(anchor='w', pady=(2, 0))
        ttk.Label(info_frame, text=f"Destination: {dest_dir}", foreground="blue", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(2, 0))
        ttk.Label(info_frame, text="Select duplicates to move (keeps the first listed file):", foreground="gray").pack(anchor='w', pady=(5, 0))
        
        delete_empty = tk.BooleanVar(value=True)
        ttk.Checkbutton(info_frame, text="Delete empty folders in source after moving", variable=delete_empty).pack(anchor='w', pady=(6, 0))
        
        # Scrollable duplicate list
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # Mouse wheel scrolling for the dialog
        def _on_mousewheel(event):
            try:
                delta = int(-1 * (event.delta / 120))
            except Exception:
                delta = -1
            canvas.yview_scroll(delta, "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        selected_files = []
        
        for idx, (file_hash, files) in enumerate(duplicates.items(), 1):
            group_frame = ttk.LabelFrame(scrollable, text=f"Duplicate Group {idx}", padding=10)
            group_frame.pack(fill='x', padx=10, pady=5)
            
            for i, file_path in enumerate(files):
                file_exists = os.path.exists(file_path)
                status = "✓" if file_exists else "✗ Missing"
                
                file_frame = ttk.Frame(group_frame)
                file_frame.pack(fill='x', pady=2)
                
                var = tk.BooleanVar(value=(i > 0 and file_exists))
                selected_files.append((var, file_path))
                
                cb = ttk.Checkbutton(file_frame, variable=var,
                                    text=f"{status} {file_path}" if i > 0 else f"KEEP: {file_path}",
                                    state='normal' if i > 0 and file_exists else 'disabled')
                cb.pack(side=tk.LEFT, fill='x', expand=True)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill='x', side='bottom')
        
        def move_to_destination():
            to_move = [path for var, path in selected_files if var.get()]
            if not to_move:
                messagebox.showinfo("No Selection", "No files selected to move")
                return
            
            response = messagebox.askyesno(
                "Confirm Move",
                f"Move {len(to_move)} duplicate file(s) to:\n{dest_dir}\n\n"
                "Original files will remain in source. Continue?"
            )
            
            if not response:
                return
            
            moved = 0
            failed = 0
            import shutil
            
            for file_path in to_move:
                try:
                    if os.path.exists(file_path):
                        fname = os.path.basename(file_path)
                        dest = os.path.join(dest_dir, fname)
                        # Handle collisions
                        base, ext = os.path.splitext(fname)
                        counter = 1
                        while os.path.exists(dest):
                            dest = os.path.join(dest_dir, f"{base} ({counter}){ext}")
                            counter += 1
                        shutil.move(file_path, dest)
                        # Update tracker
                        try:
                            self.duplicate_checker.remove_file(file_path)
                            self.duplicate_checker.add_file(dest)
                        except Exception:
                            pass
                        moved += 1
                        self.log(f"Moved: {file_path} → {dest}")
                except Exception as e:
                    failed += 1
                    self.log(f"Failed to move {file_path}: {e}")
            
            # Clean empty folders
            if delete_empty.get():
                removed = self._delete_empty_folders(source_dir)
                if removed:
                    self.log(f"Deleted {removed} empty folder(s) in source")
            
            messagebox.showinfo("Move Complete", f"Moved {moved} file(s)\nFailed: {failed}")
            dialog.destroy()
            self.log(f"Advanced scan & move complete: {moved} files moved to {dest_dir}")
        
        ttk.Button(btn_frame, text=f"Move Selected to {os.path.basename(dest_dir)}", 
                  command=move_to_destination).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        self.log(f"Showing {len(duplicates)} duplicate groups with destination: {dest_dir}")
    
    def _delete_empty_folders(self, root_dir: str) -> int:
        """Delete empty folders, including those with only hidden/system files"""
        import shutil
        removed = 0
        folders_to_remove = []
        
        # First pass: collect all directories and clean up junk files
        for r, dnames, fnames in os.walk(root_dir, topdown=False):
            # Skip the root directory itself
            if r == root_dir:
                continue
            
            try:
                # Remove junk files first
                for fname in fnames:
                    fpath = os.path.join(r, fname)
                    if fname.lower() in ['.ds_store', 'thumbs.db', 'desktop.ini', '.gitkeep', 'desktop.ini']:
                        try:
                            os.remove(fpath)
                        except:
                            pass
                
                # Re-check contents after junk removal
                try:
                    contents = os.listdir(r)
                except:
                    contents = []
                
                # If empty now, mark for removal
                if not contents:
                    folders_to_remove.append(r)
            except Exception:
                pass
        
        # Second pass: remove empty directories
        for folder in folders_to_remove:
            try:
                os.rmdir(folder)
                removed += 1
            except:
                # If rmdir fails, try force remove
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                    removed += 1
                except:
                    pass
        
        return removed
    
    def delete_all_duplicates(self):
        """Automatically delete all duplicate files, keeping only one from each group"""
        self.log("Finding duplicate files for automatic deletion...")
        duplicates = self.duplicate_checker.find_duplicates()
        
        if not duplicates:
            messagebox.showinfo("No Duplicates", "No duplicate files found! All files are unique.")
            self.log("No duplicates found")
            return
        
        # Count total files to delete
        total_to_delete = sum(len(files) - 1 for files in duplicates.values())
        
        response = messagebox.askyesno(
            "Delete All Duplicates",
            f"Found {len(duplicates)} groups of duplicates.\n"
            f"Will delete {total_to_delete} duplicate files, keeping one from each group.\n\n"
            "This action cannot be undone!\n\n"
            "Continue?"
        )
        
        if not response:
            return
        
        deleted = 0
        failed = 0
        
        for file_hash, files in duplicates.items():
            # Keep the first file, delete the rest
            for file_path in files[1:]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.duplicate_checker.remove_file(file_path)
                        deleted += 1
                        self.log(f"Deleted duplicate: {file_path}")
                    else:
                        self.log(f"File already missing: {file_path}")
                except Exception as e:
                    failed += 1
                    self.log(f"Failed to delete {file_path}: {e}")
        
        messagebox.showinfo("Deletion Complete", 
                           f"Deleted {deleted} duplicate files\n"
                           f"Failed: {failed}\n"
                           f"Kept {len(duplicates)} unique files")
        self.log(f"Auto-deleted {deleted} duplicate files, kept {len(duplicates)} unique files")
    
    def show_duplicate_stats(self):
        """Show duplicate detection statistics"""
        stats = self.duplicate_checker.get_statistics()
        
        msg = "Duplicate Detection Statistics:\n\n"
        msg += f"Total files tracked: {stats['total_files']}\n"
        msg += f"Video files: {stats['video_count']}\n"
        msg += f"Image files: {stats['image_count']}\n"
        msg += f"Other files: {stats['other_count']}\n\n"
        msg += f"Total size: {stats['total_size_mb']} MB ({stats['total_size_gb']:.2f} GB)\n\n"
        
        missing = self.duplicate_checker.verify_files_exist()
        if missing > 0:
            msg += f"⚠️ {missing} tracked files no longer exist on disk\n"
        else:
            msg += "✅ All tracked files exist on disk\n"
        
        messagebox.showinfo("Duplicate Detection Statistics", msg)
        self.log("Displayed duplicate detection statistics")
    
    def migrate_old_files(self):
        """Migrate old text files to new user management system"""
        response = messagebox.askyesno(
            "Migrate Old Data",
            "This will migrate usernames, subreddits, and websites from old text files\n"
            "to the new Active/Inactive management system.\n\n"
            "All items will be set as ACTIVE by default.\n\n"
            "Continue?"
        )
        
        if response:
            self.log("Starting migration...")
            count = self.user_manager.migrate_from_old_files()
            
            if count > 0:
                self.log(f"Migration complete! Migrated {count} items.")
                messagebox.showinfo("Migration Complete", f"Successfully migrated {count} items.\n\nRefreshing lists...")
                
                # Refresh all lists
                self.refresh_subreddit_lists()
                self.refresh_reddit_user_lists()
                self.refresh_twitter_user_lists()
                self.refresh_website_lists()
            else:
                self.log("No items to migrate or migration failed.")
                messagebox.showinfo("Migration", "No items found to migrate.")
    

def main():
    """Main entry point"""
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
