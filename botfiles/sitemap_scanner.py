"""
Sitemap scanner and gallery-dl integration module
"""
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import subprocess
import os
import json


class SitemapScanner:
    """Scans sitemaps and websites to preview available media"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scan_sitemap(self, sitemap_url, progress_callback=None):
        """
        Scan a sitemap and return all URLs found
        Returns: dict with 'urls', 'image_urls', 'video_urls', 'page_urls'
        """
        result = {
            'urls': [],
            'image_urls': [],
            'video_urls': [],
            'page_urls': [],
            'total_count': 0
        }
        
        try:
            if progress_callback:
                progress_callback(f"Scanning sitemap: {sitemap_url}")
            
            response = self.session.get(sitemap_url, timeout=30)
            response.raise_for_status()
            
            # Parse XML sitemap
            root = ET.fromstring(response.content)
            
            # Handle different sitemap namespaces
            namespaces = {
                'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                'image': 'http://www.google.com/schemas/sitemap-image/1.1',
                'video': 'http://www.google.com/schemas/sitemap-video/1.1'
            }
            
            # Check if it's a sitemap index
            sitemaps = root.findall('.//sm:sitemap/sm:loc', namespaces)
            if sitemaps:
                # It's a sitemap index, recursively fetch child sitemaps
                if progress_callback:
                    progress_callback(f"Found {len(sitemaps)} child sitemaps")
                
                for sitemap in sitemaps:
                    child_result = self.scan_sitemap(sitemap.text, progress_callback)
                    result['urls'].extend(child_result['urls'])
                    result['image_urls'].extend(child_result['image_urls'])
                    result['video_urls'].extend(child_result['video_urls'])
                    result['page_urls'].extend(child_result['page_urls'])
                
                result['total_count'] = len(result['urls'])
                return result
            
            # Get all page URLs from sitemap
            url_elements = root.findall('.//sm:url/sm:loc', namespaces)
            page_urls = [url.text for url in url_elements]
            result['page_urls'] = page_urls
            result['urls'].extend(page_urls)
            
            # Get image URLs
            image_urls = root.findall('.//image:image/image:loc', namespaces)
            for url in image_urls:
                result['image_urls'].append(url.text)
                result['urls'].append(url.text)
            
            # Get video URLs
            video_urls = root.findall('.//video:video/video:content_loc', namespaces)
            for url in video_urls:
                result['video_urls'].append(url.text)
                result['urls'].append(url.text)
            
            result['total_count'] = len(result['urls'])
            
            if progress_callback:
                progress_callback(f"Found {len(page_urls)} pages, {len(result['image_urls'])} images, {len(result['video_urls'])} videos")
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scanning sitemap: {str(e)}")
        
        return result
    
    def scan_url(self, url, progress_callback=None):
        """
        Scan a URL to find media content
        Returns: dict with 'images', 'videos', 'links'
        """
        result = {
            'images': [],
            'videos': [],
            'links': [],
            'gallery_dl_supported': False
        }
        
        try:
            if progress_callback:
                progress_callback(f"Scanning URL: {url}")
            
            # Check if gallery-dl supports this URL
            result['gallery_dl_supported'] = self.check_gallery_dl_support(url)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all images
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    full_url = urljoin(url, str(src))
                    if full_url not in result['images']:
                        result['images'].append(full_url)
            
            # Find all videos
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    full_url = urljoin(url, str(src))
                    if full_url not in result['videos']:
                        result['videos'].append(full_url)
                
                # Check source tags within video
                for source in video.find_all('source'):
                    src = source.get('src')
                    if src:
                        full_url = urljoin(url, str(src))
                        if full_url not in result['videos']:
                            result['videos'].append(full_url)
            
            # Find links to media files
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    full_url = urljoin(url, str(href))
                    if any(full_url.lower().endswith(ext) for ext in 
                          ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.mov']):
                        if full_url not in result['links']:
                            result['links'].append(full_url)
            
            total = len(result['images']) + len(result['videos']) + len(result['links'])
            if progress_callback:
                progress_callback(f"Found {len(result['images'])} images, {len(result['videos'])} videos, {len(result['links'])} media links")
                if result['gallery_dl_supported']:
                    progress_callback(f"✓ gallery-dl can download from this URL")
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scanning URL: {str(e)}")
        
        return result
    
    def check_gallery_dl_support(self, url):
        """Check if gallery-dl supports this URL"""
        try:
            # Run gallery-dl with --list-extractors to check support
            result = subprocess.run(
                ['gallery-dl', '--list-extractors'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Parse the domain from URL
                domain = urlparse(url).netloc.replace('www.', '')
                # Check if domain is in supported extractors
                return domain in result.stdout.lower()
        except:
            pass
        
        return False


class GalleryDLDownloader:
    """Use gallery-dl to download media from supported sites"""
    
    def __init__(self):
        self.gallery_dl_available = self._check_gallery_dl()
    
    def _check_gallery_dl(self):
        """Check if gallery-dl is installed"""
        try:
            result = subprocess.run(
                ['gallery-dl', '--version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def download_url(self, url, download_path, progress_callback=None):
        """
        Download media from URL using gallery-dl
        Returns: list of downloaded files
        """
        if not self.gallery_dl_available:
            if progress_callback:
                progress_callback("gallery-dl not available")
            return []
        
        downloaded_files = []
        
        try:
            if progress_callback:
                progress_callback(f"Using gallery-dl to download: {url}")
            
            # Build gallery-dl command
            cmd = [
                'gallery-dl',
                '--destination', download_path,
                '--no-part',  # Don't create .part files
                url
            ]
            
            # Run gallery-dl
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Parse output to find downloaded files
                for line in result.stdout.split('\n'):
                    if download_path in line:
                        # Extract filename from output
                        parts = line.split(download_path)
                        if len(parts) > 1:
                            filename = parts[1].strip().strip('"\'')
                            filepath = os.path.join(download_path, filename)
                            if os.path.exists(filepath):
                                downloaded_files.append(filepath)
                
                if progress_callback:
                    progress_callback(f"gallery-dl downloaded {len(downloaded_files)} files")
            else:
                if progress_callback:
                    progress_callback(f"gallery-dl error: {result.stderr[:100]}")
        
        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback("gallery-dl download timed out")
        except Exception as e:
            if progress_callback:
                progress_callback(f"gallery-dl error: {str(e)}")
        
        return downloaded_files
    
    def get_supported_sites(self):
        """Get list of sites supported by gallery-dl"""
        if not self.gallery_dl_available:
            return []
        
        try:
            result = subprocess.run(
                ['gallery-dl', '--list-extractors'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Parse extractors from output
                sites = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('gallery-dl'):
                        sites.append(line)
                return sites
        except:
            pass
        
        return []
