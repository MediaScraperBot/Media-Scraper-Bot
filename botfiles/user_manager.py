"""
Active/Inactive User Management System
Allows organizing users into active and inactive lists
Only active users are scraped
"""
import json
import os


class UserManager:
    """
    Manages active and inactive users for each platform
    """
    
    def __init__(self, file_path='botfiles/users_status.json'):
        self.file_path = file_path
        self.data = self._load_data()
    
    def _load_data(self):
        """Load user status data from disk"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._get_default_structure()
        return self._get_default_structure()
    
    def _get_default_structure(self):
        """Get default data structure"""
        return {
            'reddit': {
                'active': [],
                'inactive': []
            },
            'twitter': {
                'active': [],
                'inactive': []
            },
            'subreddits': {
                'active': [],
                'inactive': []
            },
            'websites': {
                'active': [],
                'inactive': []
            },
            'onlyfans': {
                'active': [],
                'inactive': []
            }
        }
    
    def _save_data(self):
        """Save user status data to disk"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2)
    
    def add_user(self, platform, username, active=True):
        """
        Add a user to the specified platform
        
        Args:
            platform: 'reddit', 'twitter', 'subreddits', or 'websites'
            username: Username or item to add
            active: Whether to add to active (True) or inactive (False) list
        """
        if platform not in self.data:
            return False
        
        status = 'active' if active else 'inactive'
        opposite_status = 'inactive' if active else 'active'
        
        # Remove from opposite list if exists
        if username in self.data[platform][opposite_status]:
            self.data[platform][opposite_status].remove(username)
        
        # Add to target list if not already there
        if username not in self.data[platform][status]:
            self.data[platform][status].append(username)
            self._save_data()
            return True
        
        return False
    
    def remove_user(self, platform, username):
        """
        Remove a user from both active and inactive lists
        
        Args:
            platform: 'reddit', 'twitter', 'subreddits', or 'websites'
            username: Username to remove
        """
        if platform not in self.data:
            return False
        
        removed = False
        if username in self.data[platform]['active']:
            self.data[platform]['active'].remove(username)
            removed = True
        if username in self.data[platform]['inactive']:
            self.data[platform]['inactive'].remove(username)
            removed = True
        
        if removed:
            self._save_data()
        
        return removed
    
    def move_to_active(self, platform, username):
        """Move a user from inactive to active"""
        return self.add_user(platform, username, active=True)
    
    def move_to_inactive(self, platform, username):
        """Move a user from active to inactive"""
        return self.add_user(platform, username, active=False)
    
    def set_user_status(self, platform, username, active=True):
        """Set user status (active or inactive) - alias for add_user"""
        return self.add_user(platform, username, active=active)
    
    def get_active_users(self, platform):
        """Get list of active users for a platform"""
        if platform not in self.data:
            return []
        return self.data[platform]['active'].copy()
    
    def get_inactive_users(self, platform):
        """Get list of inactive users for a platform"""
        if platform not in self.data:
            return []
        return self.data[platform]['inactive'].copy()
    
    def get_all_users(self, platform):
        """Get all users (both active and inactive) for a platform"""
        if platform not in self.data:
            return []
        return self.data[platform]['active'] + self.data[platform]['inactive']
    
    def is_active(self, platform, username):
        """Check if a user is in the active list"""
        if platform not in self.data:
            return False
        return username in self.data[platform]['active']
    
    def get_statistics(self):
        """Get statistics about users"""
        stats = {}
        for platform in self.data:
            stats[platform] = {
                'active': len(self.data[platform]['active']),
                'inactive': len(self.data[platform]['inactive']),
                'total': len(self.data[platform]['active']) + len(self.data[platform]['inactive'])
            }
        return stats
    
    def migrate_from_old_files(self, usernames_file='botfiles/usernames.txt', 
                                subreddit_file='botfiles/subreddit.txt',
                                websites_file='botfiles/websites.txt'):
        """
        Migrate users from old text files to new system
        All migrated users are set as active by default
        Skips lines starting with # (comments)
        """
        migrated_count = 0
        
        # Migrate usernames.txt (reddit:username and twitter:username)
        if os.path.exists(usernames_file):
            try:
                with open(usernames_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        
                        if ':' in line:
                            platform, username = line.split(':', 1)
                            platform = platform.strip()
                            username = username.strip()
                            if self.add_user(platform, username, active=True):
                                migrated_count += 1
            except:
                pass
        
        # Migrate subreddit.txt
        if os.path.exists(subreddit_file):
            try:
                with open(subreddit_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        subreddit = line.strip()
                        # Skip empty lines and comments
                        if not subreddit or subreddit.startswith('#'):
                            continue
                        if self.add_user('subreddits', subreddit, active=True):
                            migrated_count += 1
            except:
                pass
        
        # Migrate websites.txt
        if os.path.exists(websites_file):
            try:
                with open(websites_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        website = line.strip()
                        # Skip empty lines and comments
                        if not website or website.startswith('#'):
                            continue
                        if self.add_user('websites', website, active=True):
                            migrated_count += 1
            except:
                pass
        
        return migrated_count
