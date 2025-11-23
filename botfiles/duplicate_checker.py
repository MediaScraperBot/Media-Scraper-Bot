"""
Enhanced Duplicate Detection System
Uses file hashing to guarantee 100% duplicate detection even if files are moved
"""
import hashlib
import json
import os
from pathlib import Path


class DuplicateChecker:
    """
    Tracks downloaded files by their hash to prevent duplicates
    even if files are moved to different locations
    """
    
    def __init__(self, history_file='botfiles/file_hashes.json'):
        self.history_file = history_file
        self.file_hashes = self._load_hashes()
    
    def _load_hashes(self):
        """Load existing file hashes from disk"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_hashes(self):
        """Save file hashes to disk"""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.file_hashes, f, indent=2)
    
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """
        Calculate SHA256 hash of a file
        
        Args:
            file_path: Path to the file
            chunk_size: Size of chunks to read (for large files)
            
        Returns:
            str: Hexadecimal hash string
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            return None
    
    def is_duplicate(self, file_path, verify_exists=False):
        """
        Check if a file is a duplicate based on its hash
        
        Args:
            file_path: Path to the file to check
            verify_exists: If True, check if existing file still exists on disk
            
        Returns:
            tuple: (is_duplicate, existing_path or None)
        """
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return False, None
        
        if file_hash in self.file_hashes:
            # This file hash already exists
            existing_info = self.file_hashes[file_hash]
            existing_path = existing_info.get('path', 'unknown location')
            
            # If verify_exists is True, check if the file still exists
            if verify_exists and existing_path != 'unknown location':
                if not os.path.exists(existing_path):
                    # File was deleted, remove from tracking and allow re-download
                    del self.file_hashes[file_hash]
                    self._save_hashes()
                    return False, None
            
            return True, existing_path
        
        return False, None
    
    def is_duplicate_url(self, url, verify_exists=False):
        """
        Check if a URL has been downloaded before based on URL hash
        
        Args:
            url: URL to check
            verify_exists: If True, check if downloaded file still exists on disk
            
        Returns:
            bool: True if URL was already downloaded and file still exists (if verify_exists=True)
        """
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        
        for file_hash, info in list(self.file_hashes.items()):
            if info.get('url_hash') == url_hash:
                # If verify_exists, check if file still exists
                if verify_exists:
                    file_path = info.get('path')
                    if file_path and not os.path.exists(file_path):
                        # File was deleted, remove from tracking
                        del self.file_hashes[file_hash]
                        self._save_hashes()
                        return False
                return True
        
        return False
    
    def add_file(self, file_path, source_url=None, metadata=None):
        """
        Add a file to the duplicate checker
        
        Args:
            file_path: Path to the downloaded file
            source_url: URL where file was downloaded from
            metadata: Additional metadata (username, subreddit, etc.)
        """
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return
        
        info = {
            'path': str(file_path),
            'filename': os.path.basename(file_path),
            'size': os.path.getsize(file_path)
        }
        
        if source_url:
            info['url'] = source_url
            info['url_hash'] = hashlib.sha256(source_url.encode('utf-8')).hexdigest()
        
        if metadata:
            info['metadata'] = metadata
        
        self.file_hashes[file_hash] = info
        self._save_hashes()
    
    def scan_existing_files(self, directory, progress_callback=None):
        """
        Scan an existing directory and add all files to hash database
        Useful for tracking files that were downloaded before this feature
        
        Args:
            directory: Directory to scan
            progress_callback: Optional callback function(message)
        """
        files_added = 0
        
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                
                # Skip if already tracked
                file_hash = self.calculate_file_hash(file_path)
                if file_hash and file_hash not in self.file_hashes:
                    self.add_file(file_path)
                    files_added += 1
                    
                    if progress_callback and files_added % 10 == 0:
                        progress_callback(f"Scanned {files_added} files...")
        
        if progress_callback:
            progress_callback(f"Scan complete! Added {files_added} files to database.")
        
        return files_added
    
    def get_statistics(self):
        """Get statistics about tracked files"""
        total_files = len(self.file_hashes)
        total_size = sum(info.get('size', 0) for info in self.file_hashes.values())
        
        # Count videos vs images by file extension
        video_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
        
        video_count = 0
        image_count = 0
        other_count = 0
        
        for info in self.file_hashes.values():
            file_path = info.get('path', '')
            ext = os.path.splitext(file_path.lower())[1]
            
            if ext in video_extensions:
                video_count += 1
            elif ext in image_extensions:
                image_count += 1
            else:
                other_count += 1
        
        return {
            'total_files': total_files,
            'video_count': video_count,
            'image_count': image_count,
            'other_count': other_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2)
        }
    
    def verify_files_exist(self):
        """
        Check which tracked files still exist on disk
        Returns count of missing files
        """
        missing_count = 0
        
        for file_hash, info in list(self.file_hashes.items()):
            file_path = info.get('path')
            if file_path and not os.path.exists(file_path):
                missing_count += 1
        
        return missing_count
    
    def find_duplicates(self):
        """
        Find groups of duplicate files (same hash, different paths)
        Returns dict of {hash: [list of file paths]}
        """
        duplicates = {}
        
        # Group files by hash
        hash_groups = {}
        for file_hash, info in self.file_hashes.items():
            file_path = info.get('path')
            if file_path:
                if file_hash not in hash_groups:
                    hash_groups[file_hash] = []
                hash_groups[file_hash].append(file_path)
        
        # Keep only groups with multiple files
        for file_hash, paths in hash_groups.items():
            if len(paths) > 1:
                duplicates[file_hash] = paths
        
        return duplicates
    
    def remove_file(self, file_path):
        """
        Remove a specific file from tracking
        """
        # Find and remove the hash entry for this file path
        for file_hash, info in list(self.file_hashes.items()):
            if info.get('path') == file_path:
                del self.file_hashes[file_hash]
                self._save_hashes()
                return True
        return False
    
    def cleanup_missing_files(self):
        """
        Remove entries for files that no longer exist
        Use with caution - only if you've permanently deleted files
        """
        files_removed = 0
        
        for file_hash, info in list(self.file_hashes.items()):
            file_path = info.get('path')
            if file_path and not os.path.exists(file_path):
                del self.file_hashes[file_hash]
                files_removed += 1
        
        if files_removed > 0:
            self._save_hashes()
        
        return files_removed
    
    def clear_all(self):
        """Clear all tracked files (use with caution!)"""
        self.file_hashes = {}
        self._save_hashes()
