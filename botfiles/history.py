"""
History tracking module for downloaded content
"""
import json
import os
from datetime import datetime
from pathlib import Path


class DownloadHistory:
    """Tracks downloaded content to avoid duplicates"""
    
    def __init__(self, history_file='download_history.json'):
        self.history_file = history_file
        self.history = self.load_history()
    
    def load_history(self):
        """Load download history from JSON file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._create_empty_history()
        return self._create_empty_history()
    
    def _create_empty_history(self):
        """Create empty history structure"""
        return {
            'reddit_posts': {},      # subreddit/user -> [post_ids]
            'twitter_tweets': {},     # username -> [tweet_ids]
            'websites': {},           # url -> [media_urls]
            'last_updated': {}        # source -> timestamp
        }
    
    def save_history(self):
        """Save history to JSON file"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2)
    
    # Reddit methods
    def is_reddit_post_downloaded(self, source, post_id):
        """Check if a Reddit post has been downloaded"""
        if source not in self.history['reddit_posts']:
            return False
        return post_id in self.history['reddit_posts'][source]
    
    def add_reddit_post(self, source, post_id):
        """Mark a Reddit post as downloaded"""
        if source not in self.history['reddit_posts']:
            self.history['reddit_posts'][source] = []
        if post_id not in self.history['reddit_posts'][source]:
            self.history['reddit_posts'][source].append(post_id)
            self._update_timestamp(f"reddit:{source}")
    
    def get_reddit_post_ids(self, source):
        """Get all downloaded post IDs for a source"""
        return self.history['reddit_posts'].get(source, [])
    
    # Twitter methods
    def is_twitter_tweet_downloaded(self, username, tweet_id):
        """Check if a Twitter tweet has been downloaded"""
        if username not in self.history['twitter_tweets']:
            return False
        return str(tweet_id) in self.history['twitter_tweets'][username]
    
    def add_twitter_tweet(self, username, tweet_id):
        """Mark a Twitter tweet as downloaded"""
        if username not in self.history['twitter_tweets']:
            self.history['twitter_tweets'][username] = []
        tweet_id_str = str(tweet_id)
        if tweet_id_str not in self.history['twitter_tweets'][username]:
            self.history['twitter_tweets'][username].append(tweet_id_str)
            self._update_timestamp(f"twitter:{username}")
    
    def get_twitter_tweet_ids(self, username):
        """Get all downloaded tweet IDs for a username"""
        return self.history['twitter_tweets'].get(username, [])
    
    # Website methods
    def is_website_url_downloaded(self, website, media_url):
        """Check if a media URL from a website has been downloaded"""
        if website not in self.history['websites']:
            return False
        entries = self.history['websites'][website]
        # Support legacy list-of-strings and new list-of-dicts
        for e in entries:
            if isinstance(e, str):
                if e == media_url:
                    return True
            elif isinstance(e, dict):
                if e.get('media_url') == media_url:
                    return True
        return False
    
    def add_website_url(self, website, media_url):
        """Mark a media URL from a website as downloaded"""
        # Legacy simple append (no hash/filename)
        if website not in self.history['websites']:
            self.history['websites'][website] = []
        # avoid duplicate strings
        entries = self.history['websites'][website]
        for e in entries:
            if isinstance(e, str) and e == media_url:
                return
            if isinstance(e, dict) and e.get('media_url') == media_url:
                return
        self.history['websites'][website].append(media_url)
        self._update_timestamp(f"website:{website}")

    def add_website_entry(self, website, media_url, filename=None, sha256=None, filepath=None):
        """Add a website history entry with optional filename, filepath and sha256 hash"""
        if website not in self.history['websites']:
            self.history['websites'][website] = []
        entries = self.history['websites'][website]
        # Avoid duplicates by media_url
        for e in entries:
            if isinstance(e, dict) and e.get('media_url') == media_url:
                # update fields if missing
                if filename:
                    e.setdefault('filename', filename)
                if sha256:
                    e.setdefault('sha256', sha256)
                if filepath:
                    e.setdefault('filepath', filepath)
                return
            if isinstance(e, str) and e == media_url:
                # replace legacy string with dict
                new = {'media_url': media_url}
                if filename:
                    new['filename'] = filename
                if sha256:
                    new['sha256'] = sha256
                if filepath:
                    new['filepath'] = filepath
                entries.remove(e)
                entries.append(new)
                self._update_timestamp(f"website:{website}")
                return
        # append new dict entry
        entry = {'media_url': media_url}
        if filename:
            entry['filename'] = filename
        if sha256:
            entry['sha256'] = sha256
        if filepath:
            entry['filepath'] = filepath
        entries.append(entry)
        self._update_timestamp(f"website:{website}")

    def is_sha_downloaded(self, sha256):
        """Check if a SHA256 hash already exists in history (across all websites)"""
        if not sha256:
            return False
        for site, entries in self.history['websites'].items():
            for e in entries:
                if isinstance(e, dict) and e.get('sha256') == sha256:
                    return True
        return False

    def get_entry_by_sha(self, sha256):
        """Return (website, entry) for a given sha256 if present, else (None, None)"""
        if not sha256:
            return None, None
        for site, entries in self.history['websites'].items():
            for e in entries:
                if isinstance(e, dict) and e.get('sha256') == sha256:
                    return site, e
        return None, None
    
    def get_website_urls(self, website):
        """Get all downloaded media URLs for a website"""
        return self.history['websites'].get(website, [])
    
    # Timestamp methods
    def _update_timestamp(self, source):
        """Update the last updated timestamp for a source"""
        self.history['last_updated'][source] = datetime.now().isoformat()
    
    def get_last_updated(self, source):
        """Get the last updated timestamp for a source"""
        return self.history['last_updated'].get(source)
    
    # Maintenance methods
    def get_statistics(self):
        """Get statistics about download history"""
        stats = {
            'total_reddit_sources': len(self.history['reddit_posts']),
            'total_reddit_posts': sum(len(posts) for posts in self.history['reddit_posts'].values()),
            'total_twitter_sources': len(self.history['twitter_tweets']),
            'total_twitter_tweets': sum(len(tweets) for tweets in self.history['twitter_tweets'].values()),
            'total_websites': len(self.history['websites']),
            'total_website_urls': sum(len(urls) for urls in self.history['websites'].values())
        }
        return stats
    
    def clear_source(self, source_type, source_name):
        """Clear history for a specific source"""
        if source_type == 'reddit':
            if source_name in self.history['reddit_posts']:
                del self.history['reddit_posts'][source_name]
        elif source_type == 'twitter':
            if source_name in self.history['twitter_tweets']:
                del self.history['twitter_tweets'][source_name]
        elif source_type == 'website':
            if source_name in self.history['websites']:
                del self.history['websites'][source_name]
        
        key = f"{source_type}:{source_name}"
        if key in self.history['last_updated']:
            del self.history['last_updated'][key]
        
        self.save_history()
    
    def clear_all_history(self):
        """Clear all download history"""
        self.history = self._create_empty_history()
        self.save_history()
