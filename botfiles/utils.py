"""
Utility module for managing configuration and text files
"""
import json
import os
from pathlib import Path


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self._ensure_config_exists()
        self.config = self.load_config()
    
    def _ensure_config_exists(self):
        """Create config from template if it doesn't exist"""
        if not os.path.exists(self.config_path):
            template_path = self.config_path + '.template'
            if os.path.exists(template_path):
                # Copy template to config
                import shutil
                shutil.copy(template_path, self.config_path)
                print(f"✓ Created {self.config_path} from template")
                print("⚠️  Please configure your API credentials in Settings tab")
    
    def load_config(self):
        """Load configuration from JSON file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    def set(self, key, value):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()


class TextFileManager:
    """Manages text file lists (usernames, subreddits, websites)"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create file from template if it doesn't exist"""
        if not os.path.exists(self.filepath):
            template_path = self.filepath + '.template'
            if os.path.exists(template_path):
                # Copy template
                import shutil
                shutil.copy(template_path, self.filepath)
            else:
                # Create empty file
                Path(self.filepath).touch()
    
    def read_items(self):
        """Read all items from file (excluding comments and empty lines)"""
        items = []
        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    items.append(line)
        return items
    
    def add_item(self, item):
        """Add a new item to the file"""
        items = self.read_items()
        if item not in items:
            with open(self.filepath, 'a', encoding='utf-8') as f:
                f.write(f"{item}\n")
            return True
        return False
    
    def remove_item(self, item):
        """Remove an item from the file"""
        items = self.read_items()
        if item in items:
            items.remove(item)
            self.write_items(items)
            return True
        return False
    
    def write_items(self, items):
        """Overwrite file with new items list"""
        with open(self.filepath, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(f"{item}\n")
    
    def clear_all(self):
        """Clear all items from file"""
        self.write_items([])


def ensure_download_directory(base_path, subfolder):
    """Create and return download directory path"""
    download_path = os.path.join(base_path, subfolder)
    os.makedirs(download_path, exist_ok=True)
    return download_path

def build_download_subfolder(source_type: str, identifier: str) -> str:
    """Return relative subfolder path for a given source type and identifier.
    For subreddits and reddit users: just the name (files organized by type inside)
    For other sources: organized in type folders.
    source_type values (normalized lower): 'reddit_user', 'subreddit', 'website', 'twitter'.
    Unknown types fall back to identifier directly.
    """
    source_type = (source_type or '').lower()
    ident = sanitize_filename(identifier)
    if source_type in ('reddit_user', 'reddit'):  # reddit user profiles
        return ident  # Just username, files organized inside by type
    if source_type in ('subreddit', 'reddit_sub'):  # subreddit collections
        return ident  # Just subreddit name, files organized inside by type
    if source_type in ('website', 'site'):  # generic websites
        return os.path.join('website', ident)
    if source_type in ('twitter','x'):  # twitter/x profiles
        return os.path.join('twitter', ident)
    if source_type in ('onlyfans','of'):  # onlyfans creators
        return os.path.join('onlyfans', ident)
    return ident


def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
