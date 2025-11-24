"""
Reddit scraper module using gallery-dl (no API key required)
"""
import subprocess
import os
import json
import sys
import time
from pathlib import Path
from .utils import ensure_download_directory, sanitize_filename
from .history import DownloadHistory


class RedditScraper:
    """Scraper for Reddit content using gallery-dl"""
    
    def __init__(self, client_id=None, client_secret=None, user_agent=None, history=None, duplicate_checker=None):
        """Initialize Reddit scraper
        
        Note: client_id, client_secret, user_agent are ignored (kept for compatibility)
        gallery-dl does not require Reddit API credentials
        """
        self.history = history if history else DownloadHistory()
        self.duplicate_checker = duplicate_checker
        self._gallerydl_available = None
    
    def _is_gallerydl_available(self):
        """Check if gallery-dl is available"""
        if self._gallerydl_available is None:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "gallery_dl", "--version"],
                    capture_output=True,
                    timeout=5
                )
                self._gallerydl_available = result.returncode == 0
            except Exception:
                self._gallerydl_available = False
        return self._gallerydl_available
    
    def scrape_user(self, username, base_path, limit=None, progress_callback=None):
        """Scrape media from a Reddit user's posts
        
        Args:
            username: Reddit username to scrape
            base_path: Base download directory
            limit: Maximum number of posts to scrape (None = unlimited)
            progress_callback: Function to call with progress updates
        """
        from .utils import build_download_subfolder
        download_path = ensure_download_directory(base_path, build_download_subfolder('reddit_user', username))
        
        if not self._is_gallerydl_available():
            if progress_callback:
                progress_callback(" gallery-dl is not installed. Run: pip install gallery-dl")
            return []
        
        if progress_callback:
            progress_callback(f" Scraping u/{username} using gallery-dl...")
        
        # Construct gallery-dl command
        url = f"https://old.reddit.com/user/{username}/submitted"
        return self._run_gallerydl(url, download_path, limit, progress_callback, f"u/{username}")
    
    def scrape_subreddit(self, subreddit_name, base_path, limit=None, progress_callback=None, 
                         start_date=None, end_date=None, sort_by='hot'):
        """Scrape media from a subreddit
        
        Args:
            subreddit_name: Name of the subreddit to scrape
            base_path: Base download directory
            limit: Maximum number of posts to scrape (None = unlimited)
            progress_callback: Function to call with progress updates
            start_date: Only download posts after this date (datetime object) - Not supported by gallery-dl
            end_date: Only download posts before this date (datetime object) - Not supported by gallery-dl
            sort_by: Sorting method - 'hot', 'new', 'top', or 'rising'
        """
        from .utils import build_download_subfolder
        download_path = ensure_download_directory(base_path, build_download_subfolder('subreddit', subreddit_name))
        
        if not self._is_gallerydl_available():
            if progress_callback:
                progress_callback(" gallery-dl is not installed. Run: pip install gallery-dl")
            return []
        
        if start_date or end_date:
            if progress_callback:
                progress_callback(f" Date filtering is not supported with gallery-dl")
        
        if progress_callback:
            progress_callback(f" Scraping r/{subreddit_name} using gallery-dl (sort: {sort_by})...")
        
        # Construct gallery-dl command with sorting
        sort_map = {
            'hot': '',
            'new': '/new',
            'top': '/top',
            'rising': '/rising'
        }
        sort_suffix = sort_map.get(sort_by.lower(), '')
        url = f"https://old.reddit.com/r/{subreddit_name}{sort_suffix}"
        
        return self._run_gallerydl(url, download_path, limit, progress_callback, f"r/{subreddit_name}")
    
    def _run_gallerydl(self, url, download_path, limit, progress_callback, source_name):
        """Run gallery-dl command and track downloads
        
        Args:
            url: Reddit URL to scrape
            download_path: Directory to save files
            limit: Maximum number of items to download
            progress_callback: Progress callback function
            source_name: Name for logging (e.g., "r/pics" or "u/username")
        """
        downloaded = []
        
        try:
            # Get list of files before download
            files_before = set(os.listdir(download_path)) if os.path.exists(download_path) else set()
            
            # Build gallery-dl command
            cmd = [
                sys.executable, "-m", "gallery_dl",
                url,
                "--destination", download_path,
                "--no-part",  # Don't create .part files
            ]
            
            # Add limit if specified
            if limit:
                cmd.extend(["--range", f"1-{limit}"])
            
            # Add filename format to include post ID for history tracking
            cmd.extend([
                "--filename", "{category}_{id}_{num:>02}.{extension}",
                "--quiet"  # Reduce output noise
            ])
            
            if progress_callback:
                progress_callback(f" Running gallery-dl for {source_name}...")
            
            # Run gallery-dl
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0 and result.stderr:
                if "403" in result.stderr or "Forbidden" in result.stderr:
                    if progress_callback:
                        progress_callback(f" {source_name}: Content is private or restricted")
                elif "404" in result.stderr or "Not Found" in result.stderr:
                    if progress_callback:
                        progress_callback(f" {source_name}: Not found or doesn't exist")
                else:
                    if progress_callback:
                        progress_callback(f" {source_name}: gallery-dl error: {result.stderr[:100]}")
                return downloaded
            
            # Get list of files after download
            files_after = set(os.listdir(download_path)) if os.path.exists(download_path) else set()
            new_files = files_after - files_before
            
            # Process downloaded files
            for filename in new_files:
                filepath = os.path.join(download_path, filename)
                
                # Skip if duplicate
                if self.duplicate_checker:
                    if self.duplicate_checker.is_duplicate_file(filepath):
                        if progress_callback:
                            progress_callback(f" Skipped duplicate: {filename}")
                        try:
                            os.remove(filepath)
                        except:
                            pass
                        continue
                    # Add to duplicate tracker
                    self.duplicate_checker.add_file(filepath)
                
                # Organize by media type: pictures/videos/gifs
                import shutil
                ext = os.path.splitext(filename)[1].lower()
                
                if ext == '.gif':
                    media_folder = 'gifs'
                elif ext in ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v']:
                    media_folder = 'videos'
                elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.avif', '.heic']:
                    media_folder = 'pictures'
                else:
                    media_folder = 'other'
                
                # Create media type subfolder and move file
                media_path = os.path.join(download_path, media_folder)
                os.makedirs(media_path, exist_ok=True)
                new_filepath = os.path.join(media_path, filename)
                
                # Handle filename conflicts
                counter = 1
                base, extension = os.path.splitext(filename)
                while os.path.exists(new_filepath):
                    filename_new = f"{base}_{counter}{extension}"
                    new_filepath = os.path.join(media_path, filename_new)
                    counter += 1
                
                shutil.move(filepath, new_filepath)
                downloaded.append(new_filepath)
                
                # Extract post ID from filename (format: reddit_POSTID_01.ext)
                try:
                    parts = filename.split('_')
                    if len(parts) >= 2:
                        post_id = parts[1]
                        # Extract source from the URL or use source_name
                        source = source_name.replace('r/', '').replace('u/', '')
                        self.history.add_reddit_post(source, post_id)
                except Exception:
                    pass  # Skip history tracking if we can't parse the ID
            
            # Save history
            if downloaded:
                self.history.save_history()
            
            if progress_callback:
                if downloaded:
                    progress_callback(f" {source_name}: Downloaded {len(downloaded)} file(s)")
                else:
                    progress_callback(f"? {source_name}: No new files to download")
        
        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback(f" {source_name}: Download timeout (10 minutes)")
        except Exception as e:
            if progress_callback:
                progress_callback(f" {source_name}: Error - {str(e)}")
        
        return downloaded
