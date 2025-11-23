"""
Reddit scraper module using PRAW
"""
import praw
import requests
import os
import subprocess
import sys
import time
from urllib.parse import urlparse
from .utils import ensure_download_directory, sanitize_filename
from .history import DownloadHistory


class RedditScraper:
    """Scraper for Reddit content"""
    
    def __init__(self, client_id, client_secret, user_agent, history=None, duplicate_checker=None):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.session = requests.Session()
        self.history = history if history else DownloadHistory()
        self.duplicate_checker = duplicate_checker
        self._ytdlp_available = None
    
    def scrape_user(self, username, base_path, limit=None, progress_callback=None):
        """Scrape media from a Reddit user's posts
        
        Args:
            username: Reddit username to scrape
            base_path: Base download directory
            limit: Maximum number of posts to scrape (None = unlimited, uses pagination)
            progress_callback: Function to call with progress updates
        """
        from .utils import build_download_subfolder
        download_path = ensure_download_directory(base_path, build_download_subfolder('reddit_user', username))
        downloaded = []
        new_posts = 0
        skipped_posts = 0
        total_posts_checked = 0
        
        try:
            user = self.reddit.redditor(username)
            
            # Check if user exists and is accessible
            try:
                # This will trigger an error if user doesn't exist or is suspended
                _ = user.id
            except Exception as e:
                if progress_callback:
                    progress_callback(f"❌ u/{username}: Profile not accessible (private, suspended, or doesn't exist)")
                return downloaded
            
            if progress_callback:
                progress_callback(f"Scraping all posts from u/{username} (pagination enabled)...")
            
            # Use simple pagination (PRAW handles this with limit=None)
            try:
                posts = user.submissions.new(limit=limit)
            except Exception as e:
                if "private" in str(e).lower() or "forbidden" in str(e).lower():
                    if progress_callback:
                        progress_callback(f"🔒 u/{username}: Profile is private or restricted")
                    return downloaded
                raise
            
            for post in posts:
                total_posts_checked += 1
                
                # Check if we've already downloaded this post
                if self.history.is_reddit_post_downloaded(username, post.id):
                    skipped_posts += 1
                    # Log progress every 50 skipped posts
                    if skipped_posts % 50 == 0 and progress_callback:
                        progress_callback(f"u/{username}: Checked {total_posts_checked} posts, {skipped_posts} already downloaded")
                    continue
                
                new_posts += 1
                if progress_callback and new_posts % 10 == 0:
                    progress_callback(f"u/{username}: Found {new_posts} new posts (checked {total_posts_checked} total)")
                
                # Check if this is a v.redd.it video - use yt-dlp for better quality
                if hasattr(post, 'is_video') and post.is_video:
                    post_url = f"https://reddit.com{post.permalink}"
                    filepath = self._download_vreddit_video(post_url, download_path, post.id)
                    if filepath:
                        downloaded.append(filepath)
                        if progress_callback:
                            progress_callback(f"Downloaded video: {os.path.basename(filepath)}")
                    self.history.add_reddit_post(username, post.id)
                else:
                    # Regular media (images, gifs, external videos)
                    media_urls = self._extract_media_urls(post)
                    if media_urls:
                        for url in media_urls:
                            filepath = self._download_media(url, download_path, f"{post.id}_")
                            if filepath:
                                downloaded.append(filepath)
                        # Mark post as downloaded after processing
                        self.history.add_reddit_post(username, post.id)
                    else:
                        # Mark post as seen even if no media
                        self.history.add_reddit_post(username, post.id)
                
                # Save history periodically (every 25 new posts)
                if new_posts % 25 == 0:
                    self.history.save_history()
            
            if progress_callback:
                progress_callback(f"u/{username}: Complete! {new_posts} new posts, {skipped_posts} already seen, {total_posts_checked} total checked")
            
            # Save history after each user
            self.history.save_history()
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scraping user {username}: {str(e)}")
        
        return downloaded
    
    def scrape_subreddit(self, subreddit_name, base_path, limit=None, progress_callback=None, start_date=None, end_date=None, sort_by='hot'):
        """Scrape media from a subreddit
        
        Args:
            subreddit_name: Name of the subreddit to scrape
            base_path: Base download directory
            limit: Maximum number of posts to scrape (None = unlimited, uses pagination)
            progress_callback: Function to call with progress updates
            start_date: Only download posts after this date (datetime object)
            end_date: Only download posts before this date (datetime object)
            sort_by: Sorting method - 'hot', 'new', 'top', or 'rising'
        """
        from datetime import datetime
        
        from .utils import build_download_subfolder
        download_path = ensure_download_directory(base_path, build_download_subfolder('subreddit', subreddit_name))
        downloaded = []
        new_posts = 0
        skipped_posts = 0
        total_posts_checked = 0
        date_filtered = 0
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            date_info = ""
            if start_date or end_date:
                date_info = f" (filtering by date: {start_date.strftime('%Y-%m-%d') if start_date else 'beginning'} to {end_date.strftime('%Y-%m-%d') if end_date else 'now'})"
            
            if progress_callback:
                progress_callback(f"Scraping posts from r/{subreddit_name} (sort: {sort_by}){date_info}...")
            
            # Get posts based on sorting method
            sort_method = sort_by.lower()
            if sort_method == 'new':
                posts = subreddit.new(limit=int(limit) if limit else 100)
            elif sort_method == 'top':
                posts = subreddit.top(limit=int(limit) if limit else 100)
            elif sort_method == 'rising':
                posts = subreddit.rising(limit=int(limit) if limit else 100)
            else:  # default to 'hot'
                posts = subreddit.hot(limit=int(limit) if limit else 100)
            
            for post in posts:
                total_posts_checked += 1
                
                # Check date filtering
                if start_date or end_date:
                    post_date = datetime.fromtimestamp(post.created_utc)
                    
                    if end_date and post_date > end_date:
                        # Post is too new, skip it
                        date_filtered += 1
                        continue
                    
                    if start_date and post_date < start_date:
                        # Post is too old, we can stop since posts are sorted by new
                        if progress_callback:
                            progress_callback(f"r/{subreddit_name}: Reached posts older than start date, stopping")
                        break
                    
                    date_filtered += 1
                total_posts_checked += 1
                
                # Check if we've already downloaded this post
                if self.history.is_reddit_post_downloaded(subreddit_name, post.id):
                    skipped_posts += 1
                    # Log progress every 50 skipped posts
                    if skipped_posts % 50 == 0 and progress_callback:
                        progress_callback(f"r/{subreddit_name}: Checked {total_posts_checked} posts, {skipped_posts} already downloaded")
                    continue
                
                new_posts += 1
                if progress_callback and new_posts % 10 == 0:
                    progress_callback(f"r/{subreddit_name}: Found {new_posts} new posts (checked {total_posts_checked} total)")
                
                # Check if this is a v.redd.it video - use yt-dlp for better quality
                if hasattr(post, 'is_video') and post.is_video:
                    post_url = f"https://reddit.com{post.permalink}"
                    filepath = self._download_vreddit_video(post_url, download_path, post.id)
                    if filepath:
                        downloaded.append(filepath)
                        if progress_callback:
                            progress_callback(f"Downloaded video: {os.path.basename(filepath)}")
                    self.history.add_reddit_post(subreddit_name, post.id)
                else:
                    # Regular media (images, gifs, external videos)
                    media_urls = self._extract_media_urls(post)
                    if media_urls:
                        for url in media_urls:
                            filepath = self._download_media(url, download_path, f"{post.id}_")
                            if filepath:
                                downloaded.append(filepath)
                        # Mark post as downloaded after processing
                        self.history.add_reddit_post(subreddit_name, post.id)
                    else:
                        # Mark post as seen even if no media
                        self.history.add_reddit_post(subreddit_name, post.id)
                
                # Save history periodically (every 25 new posts)
                if new_posts % 25 == 0:
                    self.history.save_history()
            
            if progress_callback:
                filter_info = f", {date_filtered} date-filtered" if (start_date or end_date) else ""
                progress_callback(f"r/{subreddit_name}: Complete! {new_posts} new posts, {skipped_posts} already seen{filter_info}, {total_posts_checked} total checked")
            
            # Save history after each subreddit
            self.history.save_history()
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scraping subreddit {subreddit_name}: {str(e)}")
        
        return downloaded
    
    def _extract_media_urls(self, post):
        """Extract media URLs from a Reddit post"""
        urls = []
        
        # Direct image/video URL
        if hasattr(post, 'url'):
            url = post.url
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.mov']):
                urls.append(url)
            
            # Reddit hosted video (v.redd.it)
            elif hasattr(post, 'is_video') and post.is_video:
                if hasattr(post, 'media') and post.media:
                    video_data = post.media.get('reddit_video', {})
                    # Try to get highest quality video URL
                    video_url = video_data.get('fallback_url') or video_data.get('dash_url') or video_data.get('hls_url')
                    if video_url:
                        urls.append(video_url)
            
            # Check for v.redd.it links
            elif 'v.redd.it' in url:
                urls.append(url)
            
            # Check for external video hosts (these will be handled by yt-dlp if not direct)
            elif any(host in url for host in ['imgur.com', 'gfycat.com', 'redgifs.com', 'streamable.com']):
                urls.append(url)
        
        # Gallery posts
        if hasattr(post, 'is_gallery') and post.is_gallery:
            if hasattr(post, 'media_metadata'):
                for item_id, item_data in post.media_metadata.items():
                    if item_data.get('e') in ['Image', 'AnimatedImage']:
                        url = item_data.get('s', {}).get('u') or item_data.get('s', {}).get('gif')
                        if url:
                            # Unescape HTML entities in URL
                            url = url.replace('&amp;', '&')
                            urls.append(url)
        
        # Check for crosspost video
        if hasattr(post, 'crosspost_parent_list') and len(post.crosspost_parent_list) > 0:
            parent = post.crosspost_parent_list[0]
            if parent.get('is_video'):
                video_data = parent.get('media', {}).get('reddit_video', {})
                video_url = video_data.get('fallback_url')
                if video_url:
                    urls.append(video_url)
        
        return urls
    
    def _is_ytdlp_available(self):
        """Check if yt-dlp is available"""
        if self._ytdlp_available is None:
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "yt_dlp", "--version"],
                    capture_output=True,
                    timeout=5
                )
                self._ytdlp_available = (result.returncode == 0)
            except Exception:
                self._ytdlp_available = False
        return self._ytdlp_available
    
    def _download_vreddit_video(self, post_url, download_path, post_id):
        """Download v.redd.it video using yt-dlp (handles audio+video merging)"""
        if not self._is_ytdlp_available():
            return None
        
        try:
            # Construct output template
            output_template = os.path.join(download_path, f"{post_id}_%(title).80s.%(ext)s")
            
            cmd = [
                sys.executable, "-m", "yt_dlp",
                post_url,
                "-o", output_template,
                "--no-playlist",
                "--merge-output-format", "mp4",
                "--quiet",
                "--no-warnings"
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode == 0:
                # Find the downloaded file
                for file in os.listdir(download_path):
                    if file.startswith(post_id):
                        return os.path.join(download_path, file)
            
            return None
        except Exception as e:
            print(f"yt-dlp download failed: {e}")
            return None
    
    def _download_media(self, url, download_path, prefix=""):
        """Download media file from URL (with yt-dlp fallback for video sites)"""
        # Check if this is an external video site that needs yt-dlp
        external_hosts = ['redgifs.com', 'gfycat.com', 'imgur.com', 'streamable.com']
        if any(host in url for host in external_hosts):
            # Try yt-dlp first for these sites
            if self._is_ytdlp_available():
                try:
                    output_template = os.path.join(download_path, f"{prefix}%(title).80s.%(ext)s")
                    cmd = [
                        sys.executable, "-m", "yt_dlp",
                        url,
                        "-o", output_template,
                        "--no-playlist",
                        "--quiet",
                        "--no-warnings"
                    ]
                    result = subprocess.run(cmd, capture_output=True, timeout=60)
                    if result.returncode == 0:
                        # Find the downloaded file
                        for file in os.listdir(download_path):
                            if file.startswith(prefix):
                                full_path = os.path.join(download_path, file)
                                # Check if file was just created
                                if os.path.getmtime(full_path) > (time.time() - 60):
                                    return full_path
                except Exception:
                    pass  # Fall through to regular download
        
        try:
            # Use longer timeout for videos
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Get filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or filename == '':
                filename = f"media_{hash(url) % 10000}"
            filename = sanitize_filename(prefix + filename)
            
            # Ensure we have an extension
            if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm']):
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        filename += '.jpg'
                    elif 'png' in content_type:
                        filename += '.png'
                    elif 'gif' in content_type:
                        filename += '.gif'
                    else:
                        filename += '.jpg'
                elif 'video' in content_type:
                    if 'webm' in content_type:
                        filename += '.webm'
                    else:
                        filename += '.mp4'
                else:
                    # Try to determine from URL
                    if 'v.redd.it' in url or 'DASH_' in url:
                        filename += '.mp4'
                    else:
                        return None  # Skip unknown types
            
            filepath = os.path.join(download_path, filename)
            
            # Skip if file already exists
            if os.path.exists(filepath):
                return None
            
            # Check if URL already downloaded (duplicate check)
            if self.duplicate_checker and self.duplicate_checker.is_duplicate_url(url, verify_exists=True):
                print(f"Skipping duplicate URL: {url}")
                return None
            
            # Download file with progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        # Log progress for large files
                        if total_size > 0 and total_size > 5000000:  # Files over 5MB
                            progress = (downloaded_size / total_size) * 100
                            if progress % 25 == 0:  # Log at 25% intervals
                                print(f"Downloading {filename}: {progress:.0f}%")
            
            # Add to duplicate tracker after successful download
            if self.duplicate_checker:
                self.duplicate_checker.add_file(filepath, source_url=url)
            
            return filepath
        
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return None
