"""
Twitter/X scraper module using Tweepy
"""
import tweepy
import requests
import os
from typing import Optional
from urllib.parse import urlparse
from .utils import ensure_download_directory, sanitize_filename
from .history import DownloadHistory


class TwitterScraper:
    """Scraper for Twitter/X content"""
    
    def __init__(self, bearer_token=None, api_key=None, api_secret=None, 
                 access_token=None, access_token_secret=None, history=None, duplicate_checker=None):
        """Initialize Twitter scraper with API credentials"""
        
        # Try to use API v2 with bearer token
        if bearer_token:
            self.client = tweepy.Client(bearer_token=bearer_token)
        elif api_key and api_secret:
            # Fallback to API v1.1
            auth = tweepy.OAuth1UserHandler(
                api_key, api_secret,
                access_token, access_token_secret
            )
            self.api = tweepy.API(auth)
            self.client = None
        else:
            raise ValueError("Twitter API credentials are required")
        
        self.session = requests.Session()
        self.history = history if history else DownloadHistory()
        self.duplicate_checker = duplicate_checker
    
    def scrape_user(self, username, base_path, limit: Optional[int] = 100, progress_callback=None):
        """Scrape media from a Twitter user's tweets. Pass limit=None for unlimited.
        
        Args:
            username: Twitter handle or profile URL
            base_path: Download directory
            limit: Max tweets to scan (None for unlimited)
            progress_callback: Optional callback for progress updates
        """
        # Normalize username (support full profile URLs or @handle input)
        norm_username = self._normalize_username(username)
        folder_name = sanitize_filename(f"twitter_{norm_username}")
        from .utils import build_download_subfolder
        download_path = ensure_download_directory(base_path, build_download_subfolder('twitter', folder_name))
        downloaded = []
        new_tweets = 0
        skipped_tweets = 0
        unlimited = (limit is None)
        
        try:
            if self.client:
                # API v2 approach
                user = self.client.get_user(username=norm_username)
                if not hasattr(user, 'data') or not user.data:  # type: ignore
                    if progress_callback:
                        progress_callback(f"User {username} not found")
                    return downloaded
                
                max_results = 100 if unlimited else min(limit, 100)
                tweets = self.client.get_users_tweets(
                    id=user.data.id,  # type: ignore
                    max_results=max_results,
                    tweet_fields=['attachments'],
                    media_fields=['url', 'preview_image_url'],
                    expansions=['attachments.media_keys']
                )
                
                if hasattr(tweets, 'data') and tweets.data:  # type: ignore
                    media_dict = {}
                    if hasattr(tweets, 'includes') and tweets.includes and 'media' in tweets.includes:  # type: ignore
                        for media in tweets.includes['media']:  # type: ignore
                            media_dict[media.media_key] = media  # type: ignore
                    
                    for tweet in tweets.data:  # type: ignore
                        # Check if already downloaded
                        if self.history.is_twitter_tweet_downloaded(norm_username, tweet.id):
                            skipped_tweets += 1
                            continue
                        
                        new_tweets += 1
                        if progress_callback:
                            progress_callback(f"Scanning @{norm_username}: Tweet {tweet.id}")
                        
                        has_media = False
                        if hasattr(tweet, 'attachments') and tweet.attachments:
                            media_keys = tweet.attachments.get('media_keys', [])
                            for media_key in media_keys:
                                media = media_dict.get(media_key)
                                if media:
                                    url = getattr(media, 'url', None)
                                    if url:
                                        has_media = True
                                        filepath = self._download_media(url, download_path, f"{tweet.id}_")
                                        if filepath:
                                            downloaded.append(filepath)
                        
                        # Mark tweet as processed
                        self.history.add_twitter_tweet(norm_username, tweet.id)
            else:
                # API v1.1 fallback
                count = 200 if unlimited else limit
                tweets = self.api.user_timeline(screen_name=norm_username, count=count, 
                                                include_rts=False, tweet_mode='extended')
                
                for tweet in tweets:
                    # Check if already downloaded
                    if self.history.is_twitter_tweet_downloaded(norm_username, tweet.id):
                        skipped_tweets += 1
                        continue
                    
                    new_tweets += 1
                    if progress_callback:
                        progress_callback(f"Scanning @{norm_username}: Tweet {tweet.id}")
                    
                    has_media = False
                    if 'media' in tweet.entities:
                        for media in tweet.entities['media']:
                            media_url = media.get('media_url_https', media.get('media_url'))
                            if media_url:
                                has_media = True
                                filepath = self._download_media(media_url, download_path, f"{tweet.id}_")
                                if filepath:
                                    downloaded.append(filepath)
                    
                    # Mark tweet as processed
                    self.history.add_twitter_tweet(norm_username, tweet.id)
            
            if progress_callback:
                progress_callback(f"@{norm_username}: {new_tweets} new tweets, {skipped_tweets} already seen")
            
            # Save history after each user
            self.history.save_history()
        
        except Exception as e:
            # Attempt fallback with snscrape if API auth fails
            err_msg = str(e)
            if ('401' in err_msg or 'Unauthorized' in err_msg):
                if progress_callback:
                    progress_callback(f"API unauthorized for {norm_username}, trying snscrape fallback...")
                fallback = self._fallback_snscrape(norm_username, download_path, limit, progress_callback)
                downloaded.extend(fallback)
                if progress_callback:
                    progress_callback(f"Fallback: downloaded {len(fallback)} files from @{norm_username}")
                # Save history after fallback
                self.history.save_history()
            else:
                if progress_callback:
                    progress_callback(f"Error scraping Twitter user {norm_username}: {err_msg}")
        
        return downloaded

    def _normalize_username(self, raw: str) -> str:
        """Accepts @handle, handle, or full https://x.com/handle / https://twitter.com/handle URL.
        Returns sanitized handle (only letters, numbers, underscore)."""
        try:
            raw = (raw or '').strip()
            raw = raw.lstrip('@')
            if raw.startswith('http://') or raw.startswith('https://'):
                parsed = urlparse(raw)
                # path like /SomeUser or /SomeUser/extra -> take first non-empty segment
                segments = [seg for seg in parsed.path.split('/') if seg]
                if segments:
                    raw = segments[0]
            # Remove query params / fragments
            raw = raw.split('?')[0].split('#')[0]
            import re
            cleaned = re.sub(r'[^A-Za-z0-9_]', '_', raw)
            return cleaned or 'user'
        except Exception:
            return 'user'
    
    def _download_media(self, url, download_path, prefix=""):
        """Download media file from URL"""
        try:
            # Get the highest quality version for Twitter images
            if ':' in url and 'pbs.twimg.com' in url:
                url = url.split('?')[0] + '?format=jpg&name=large'
            
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Get filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path.split('?')[0])
            filename = sanitize_filename(prefix + filename)
            
            # Ensure we have an extension
            if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4']):
                filename += '.jpg'
            
            filepath = os.path.join(download_path, filename)
            
            # Skip if file already exists
            if os.path.exists(filepath):
                return None
            
            # Check if URL already downloaded (duplicate check)
            if self.duplicate_checker and self.duplicate_checker.is_duplicate_url(url, verify_exists=True):
                print(f"Skipping duplicate URL: {url}")
                return None
            
            # Download file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Add to duplicate tracker after successful download
            if self.duplicate_checker:
                self.duplicate_checker.add_file(filepath, source_url=url)
            
            return filepath
        
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return None

    def _fallback_snscrape(self, username, download_path, limit, progress_callback=None):
        """Fallback scraping using snscrape when API unavailable."""
        results = []
        try:
            sntwitter = self._ensure_snscrape(progress_callback)
            if not sntwitter:
                if progress_callback:
                    progress_callback("snscrape not available and auto-install failed.")
                return results
            if progress_callback:
                if limit:
                    progress_callback(f"Using snscrape to fetch tweets from @{username}... (scanning up to {limit} tweets)")
                else:
                    progress_callback(f"⚡ Using snscrape to fetch ALL tweets from @{username}... (unlimited mode)")
            
            tweets_checked = 0
            media_tweets = 0
            rate_limit_errors = 0
            import time
            
            scraper = sntwitter.TwitterUserScraper(username)
            for tweet in scraper.get_items():
                if limit and tweets_checked >= limit:
                    break
                tweets_checked += 1
                media_list = getattr(tweet, 'media', []) or []
                if media_list:
                    media_tweets += 1
                    for media in media_list:
                        # Photos / GIFs
                        url = getattr(media, 'fullUrl', None) or getattr(media, 'url', None)
                        # Videos have variants list; choose highest bitrate
                        if not url and hasattr(media, 'variants'):
                            best = None
                            for v in media.variants:
                                vb = getattr(v, 'bitrate', 0) or 0
                                if getattr(v, 'url', None):
                                    if not best or vb > best[0]:
                                        best = (vb, v.url)
                            if best:
                                url = best[1]
                        if url:
                            fp = self._download_media(url, download_path, f"{getattr(tweet,'id',tweets_checked)}_")
                            if fp:
                                results.append(fp)
                                if progress_callback and len(results) % 10 == 0:
                                    progress_callback(f"Progress: {len(results)} files downloaded...")
                
                # Rate limit backoff every 50 tweets
                if tweets_checked % 50 == 0 and tweets_checked > 0:
                    if progress_callback:
                        progress_callback(f"Rate limit pause... ({tweets_checked} tweets checked)")
                    time.sleep(2)
            
            if progress_callback:
                if rate_limit_errors > 0:
                    progress_callback(f"⚠️ Encountered {rate_limit_errors} rate limit errors")
                progress_callback(f"Scanned {tweets_checked} tweets, found {media_tweets} with media, downloaded {len(results)} files")
            return results
        except Exception as e:
            err = f"snscrape fallback failed for {username}: {e}"
            if progress_callback:
                progress_callback(err)
            else:
                print(err)
            return results

    def _ensure_snscrape(self, progress_callback=None):
        """Ensure snscrape is installed and importable. Returns module or None."""
        try:
            import snscrape.modules.twitter as sntwitter  # type: ignore
            return sntwitter
        except ImportError:
            msg = "snscrape not installed. Attempting automatic installation..."
            if progress_callback:
                progress_callback(msg)
            else:
                print(msg)
            try:
                import subprocess, sys
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'snscrape'])
                import snscrape.modules.twitter as sntwitter  # type: ignore
                msg = "snscrape installed successfully."
                if progress_callback:
                    progress_callback(msg)
                else:
                    print(msg)
                return sntwitter
            except Exception as e:
                msg = f"Automatic installation of snscrape failed: {e}"
                if progress_callback:
                    progress_callback(msg)
                else:
                    print(msg)
                return None
