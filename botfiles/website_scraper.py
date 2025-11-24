"""
Generic website scraper with sitemap support
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import re
import xml.etree.ElementTree as ET
import asyncio
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import warnings
import logging
from .utils import ensure_download_directory, sanitize_filename
from .history import DownloadHistory
from .sitemap_scanner import GalleryDLDownloader
from .download_queue import DownloadQueue

# Suppress Playwright cleanup warnings and errors
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

# Suppress asyncio and playwright error logging
logging.getLogger('playwright').setLevel(logging.CRITICAL)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)


class WebsiteScraper:
    """Scraper for generic websites and sitemaps

    Args:
        history: DownloadHistory instance
        max_workers: concurrency for downloads
        aggressive_popup: if True, perform aggressive popup / overlay removal during Playwright rendering
    """
    
    def __init__(self, history=None, max_workers=3, aggressive_popup=True, duplicate_checker=None, cookies=None, custom_headers=None):
        self.session = requests.Session()
        # Optimize connection pooling for faster downloads
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Set default headers with more complete browser mimicry
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        # Apply custom cookies if provided (format: "cookie1=value1; cookie2=value2")
        if cookies:
            try:
                cookie_dict = {}
                for cookie in cookies.split(';'):
                    cookie = cookie.strip()
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        cookie_dict[name.strip()] = value.strip()
                for name, value in cookie_dict.items():
                    self.session.cookies.set(name, value)
            except Exception:
                pass  # Silently ignore malformed cookies
        
        # Apply custom headers if provided (format: one per line "Header-Name: value")
        if custom_headers:
            try:
                for line in custom_headers.strip().split('\n'):
                    line = line.strip()
                    if ':' in line:
                        name, value = line.split(':', 1)
                        self.session.headers[name.strip()] = value.strip()
            except Exception:
                pass  # Silently ignore malformed headers
        
        self.history = history if history else DownloadHistory()
        self.duplicate_checker = duplicate_checker
        self.gallery_dl = GalleryDLDownloader()
        self._playwright_available = None
        self._playwright = None
        self._browser = None
        self.max_workers = max_workers  # Concurrent download threads
        self.aggressive_popup = aggressive_popup

    def _is_image_url(self, url):
        """Check if URL points to a likely image file"""
        if not url:
            return False
        clean_url = url.split('?')[0].split('#')[0].lower()
        return clean_url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.bmp'))

    def _compute_sha256(self, filepath, block_size=65536):
        """Compute SHA256 for a file and return hex digest"""
        try:
            import hashlib
            h = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for block in iter(lambda: f.read(block_size), b''):
                    h.update(block)
            return h.hexdigest()
        except Exception:
            return None

    def _record_history(self, website, media_url, filepath):
        """Record a downloaded file in history with filename and sha256 when available."""
        try:
            filename = os.path.basename(filepath) if filepath else None
            sha = None
            if filepath and os.path.exists(filepath):
                sha = self._compute_sha256(filepath)
            # prefer add_website_entry when we have metadata
            try:
                if sha or filename:
                    self.history.add_website_entry(website, media_url, filename=filename, sha256=sha)
                else:
                    self.history.add_website_url(website, media_url)
            except Exception:
                # fallback to legacy method
                self.history.add_website_url(website, media_url)
        except Exception:
            try:
                self.history.add_website_url(website, media_url)
            except Exception:
                pass

    def _media_subdir_for(self, media_url, base_download_path, force_video=False):
        """Return (target_dir, kind) for a media URL based on extension or hints.

        Creates the directory if it doesn't exist.
        """
        video_exts = ['.mp4', '.webm', '.m3u8', '.mov', '.avi', '.mkv', '.flv']
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.bmp']
        gif_exts = ['.gif']
        lower = (media_url or '').lower()

        kind = 'others'
        if force_video:
            kind = 'videos'
        elif any(lower.endswith(ext) for ext in video_exts) or any(ext in lower for ext in video_exts):
            kind = 'videos'
        elif any(lower.endswith(ext) for ext in gif_exts):
            kind = 'gifs'
        elif any(lower.endswith(ext) for ext in image_exts):
            kind = 'images'
        else:
            # default: put into videos if link looks like a file.php or download wrapper
            if 'file.php' in lower or 'download' in lower or force_video:
                kind = 'videos'
            else:
                kind = 'others'

        target = os.path.join(base_download_path, kind)
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass
        return target, kind
    
    def _parse_url_entry(self, url_entry):
        """Parse URL entry which may include custom folder name
        Format: 'URL' or 'URL FolderName'
        Returns: (url, custom_folder_name or None)
        """
        parts = url_entry.strip().split(None, 1)  # Split on first whitespace
        url = parts[0]
        custom_name = parts[1] if len(parts) > 1 else None
        return url, custom_name
    
    def scrape_url(self, url_entry, base_path, progress_callback=None, max_pages=50, scroll_count=5, collect_only=False):
        """Scrape media from a URL or sitemap.

        Args:
            url_entry: Either "URL" or "URL CustomFolderName".
            base_path: Root download directory.
            progress_callback: Optional logger callable.
            max_pages: Pagination limit for HTML pages.
            scroll_count: Scroll iterations for Playwright rendering.
            collect_only: When True, do not download immediately – return
                metadata dicts describing every media file discovered.
        Returns:
            List of downloaded file paths (default) or list of discovery
            dicts when collect_only=True.
        """
        url, custom_name = self._parse_url_entry(url_entry)
        
        # Determine if it's a sitemap
        if 'sitemap' in url.lower() or url.endswith('.xml'):
            return self.scrape_sitemap(
                url,
                base_path,
                progress_callback,
                custom_name,
                collect_only=collect_only,
                max_pages=max_pages,
                scroll_count=scroll_count,
            )
        else:
            return self.scrape_page(
                url,
                base_path,
                progress_callback,
                custom_name,
                max_pages=max_pages,
                scroll_count=scroll_count,
                collect_only=collect_only,
            )
    
    def scrape_sitemap(
        self,
        sitemap_url,
        base_path,
        progress_callback=None,
        custom_name=None,
        collect_only=False,
        max_pages=50,
        scroll_count=5,
    ):
        """Parse sitemap and scrape all URLs."""
        results = []
        
        try:
            if progress_callback:
                progress_callback(f"Fetching sitemap: {sitemap_url}")
            
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
            
            urls = []
            
            # Check if it's a sitemap index
            sitemaps = root.findall('.//sm:sitemap/sm:loc', namespaces)
            if sitemaps:
                # It's a sitemap index, recursively fetch child sitemaps
                for sitemap in sitemaps:
                    child_urls = self.scrape_sitemap(
                        sitemap.text,
                        base_path,
                        progress_callback,
                        custom_name,
                        collect_only=collect_only,
                        max_pages=max_pages,
                        scroll_count=scroll_count,
                    )
                    results.extend(child_urls)
                return results
            
            # Get all URLs from sitemap
            url_elements = root.findall('.//sm:url/sm:loc', namespaces)
            urls = [url.text for url in url_elements]
            
            # Also check for image:image and video:video elements
            image_urls = root.findall('.//image:image/image:loc', namespaces)
            urls.extend([url.text for url in image_urls])
            
            video_urls = root.findall('.//video:video/video:content_loc', namespaces)
            urls.extend([url.text for url in video_urls])
            
            # Create folder name from custom name or domain
            if custom_name:
                folder_name = sanitize_filename(custom_name)
            else:
                domain = urlparse(sitemap_url).netloc.replace('www.', '')
                folder_name = sanitize_filename(domain)
            from .utils import build_download_subfolder
            download_path = ensure_download_directory(base_path, build_download_subfolder('website', folder_name))
            
            # Limit based on max_pages (use it as max URLs to scrape from sitemap)
            # If max_pages is small (like default 10), increase it for sitemap scraping
            url_limit = max(max_pages * 10, 100) if max_pages < 50 else max_pages * 10
            
            if progress_callback:
                progress_callback(f"Processing up to {min(len(urls), url_limit)} URLs from sitemap (found {len(urls)} total)")
                progress_callback(f"Using {self.max_workers} concurrent workers for faster scraping")
            
            # Process URLs concurrently for faster sitemap scraping
            urls_to_process = urls[:url_limit]
            
            if collect_only:
                # In collect_only mode, process URLs concurrently
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_url = {
                        executor.submit(
                            self.scrape_page,
                            url,
                            download_path,
                            None,
                            max_pages=max_pages,
                            scroll_count=scroll_count,
                            collect_only=collect_only,
                            custom_name=None,
                        ): url for url in urls_to_process
                    }
                    
                    for idx, future in enumerate(as_completed(future_to_url), 1):
                        url = future_to_url[future]
                        try:
                            if progress_callback:
                                progress_callback(f"[{idx}/{len(urls_to_process)}] Processing: {str(url)[:60]}...")
                            files = future.result()
                            results.extend(files)
                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"Error processing {url}: {str(e)[:100]}")
            else:
                # Sequential processing when downloading immediately
                for idx, url in enumerate(urls_to_process, 1):
                    if progress_callback:
                        progress_callback(f"[{idx}/{len(urls_to_process)}] Scraping: {str(url)[:60]}...")
                    files = self.scrape_page(
                        url,
                        download_path,
                        None,
                        max_pages=max_pages,
                        scroll_count=scroll_count,
                        collect_only=collect_only,
                        custom_name=None,
                    )
                    results.extend(files)
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scraping sitemap {sitemap_url}: {str(e)}")

        return results
    
    async def _render_page_with_playwright(self, url, progress_callback=None, scroll_count=5):
        """Render page with JavaScript using Playwright, handle infinite scroll, and extract media URLs
        
        Args:
            url: URL to render
            progress_callback: Callback for progress updates
            scroll_count: Number of times to scroll down (default 5, for infinite scroll sites)
        """
        try:
            from playwright.async_api import async_playwright
            
            if progress_callback:
                progress_callback(f"Rendering JavaScript page: {url[:60]}...")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set viewport size for better rendering
                await page.set_viewport_size({"width": 1920, "height": 1080})
                
                media_urls = set()
                video_urls = set()
                
                # Intercept network requests to catch video URLs
                async def handle_request(request):
                    req_url = request.url
                    # Check for video extensions or content types
                    # Exclude thumbnails and image previews
                    lower_url = req_url.lower()
                    if any(ext in lower_url for ext in ['.mp4', '.webm', '.m3u8', '.mov', '.avi', '.mkv', '.flv']):
                        # Filter out obvious thumbnails (only when URL is an image)
                        if any(pattern in lower_url for pattern in ['thumb', 'preview', 'poster', '/t/', '/preview/']) and self._is_image_url(lower_url):
                            return
                        video_urls.add(req_url)
                        media_urls.add(req_url)
                
                async def handle_response(response):
                    try:
                        content_type = response.headers.get('content-type', '').lower()
                        req_url = response.url
                        
                        # Capture actual video content - including HLS/DASH streams
                        if ('video/' in content_type or 
                            'mpegurl' in content_type or 
                            'application/x-mpegurl' in content_type or
                            'application/vnd.apple.mpegurl' in content_type or
                            'application/dash+xml' in content_type):
                            # Filter out thumbnails (only if URL points to an image)
                            if any(pattern in req_url.lower() for pattern in ['thumb', 'preview', 'poster', '/t/', '/preview/']) and self._is_image_url(req_url):
                                return
                            video_urls.add(req_url)
                            media_urls.add(req_url)
                        
                        # Also check for large file sizes (videos are typically large)
                        content_length = response.headers.get('content-length')
                        if content_length and int(content_length) > 500000:  # > 500KB
                            if any(ext in req_url.lower() for ext in ['.mp4', '.webm', '.mov']):
                                video_urls.add(req_url)
                                media_urls.add(req_url)
                    except:
                        pass
                
                page.on('request', handle_request)
                page.on('response', handle_response)
                
                # Navigate with longer timeout
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                except Exception as e:
                    # If navigation times out, continue anyway - page may be loaded
                    if progress_callback:
                        progress_callback(f"Navigation timeout (page may still be usable): {str(e)[:100]}")
                
                # Wait for initial content to load
                await page.wait_for_timeout(3000)

                # Attach dialog auto-dismiss (alerts, confirms, prompts)
                try:
                    page.on('dialog', lambda dialog: asyncio.create_task(dialog.dismiss()))
                except Exception:
                    pass

                # Optional: block common ad / tracking domains that frequently spawn popups
                ad_domains = [
                    'doubleclick.net','googlesyndication.com','adservice.google.com','adnxs.com',
                    'ads.yahoo.com','taboola.com','outbrain.com','popads.net','exosrv.com','trafficjunky.net'
                ]
                async def route_block(route):
                    try:
                        if any(d in route.request.url for d in ad_domains):
                            await route.abort()
                            return
                    except Exception:
                        pass
                    await route.continue_()
                try:
                    await page.route('**/*', route_block)
                except Exception:
                    pass

                # Define a reusable JS snippet to close/remove popups & overlays
                popup_cleanup_js = r'''(() => {
                    const killWords = [
                        'modal','overlay','popup','consent','advert','adblock','newsletter','subscribe','signup',
                        'cookie','push','offer','promo','splash','interstitial','paywall','agegate','age-gate',
                        'captcha','verify','verification','tracking','gdpr','ccpa','privacy'
                    ];
                    const closeWords = ['close','dismiss','x','×','no thanks','skip','decline','later','got it','accept'];
                    const removalSelectors = [
                        '.modal','[id*="modal"]','.popup','[class*="popup"]','[id*="popup"]','.overlay','[class*="overlay"]',
                        '#overlay','[id*="overlay"]','[class*="dialog"]','.dialog','[class*="consent"]','[id*="consent"]',
                        '[class*="newsletter"]','[id*="newsletter"]','[class*="subscribe"]','[id*="subscribe"]','[class*="paywall"]',
                        '[class*="agegate"]','[id*="agegate"]','[class*="interstitial"]','[id*="interstitial"]','[class*="captcha"]',
                        'iframe[title*="ad"]','iframe[src*="ad"]'
                    ];
                    function shouldRemove(el){
                        try {
                            const style = getComputedStyle(el);
                            if (style.position === 'fixed' || style.zIndex > 5000) return true;
                            const c = (el.className||'').toLowerCase();
                            const id = (el.id||'').toLowerCase();
                            return killWords.some(w => c.includes(w) || id.includes(w));
                        } catch(e){ return false; }
                    }
                    removalSelectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            const closeBtn = el.querySelector('[aria-label="Close"], .close, button.close, [class*="close"], [title="Close"], .modal-close, [data-close]');
                            if (closeBtn) { try { closeBtn.click(); } catch(e){} }
                            if (shouldRemove(el)) { try { el.remove(); } catch(e){} }
                        });
                    });
                    // Generic high z-index elements
                    [...document.querySelectorAll('body *')].forEach(el => {
                        try {
                            const z = parseInt(getComputedStyle(el).zIndex||'0',10);
                            if (z > 6000) { el.remove(); }
                        } catch(e){}
                    });
                    // Click standalone dismiss/close buttons
                    document.querySelectorAll('button, a').forEach(el => {
                        const txt = (el.textContent||'').trim().toLowerCase();
                        const aria = (el.getAttribute('aria-label')||'').toLowerCase();
                        if (closeWords.some(w => txt === w || txt.includes(w) || aria.includes(w))) {
                            try { el.click(); } catch(e){}
                        }
                    });
                    // Restore body scrolling if disabled by overlay
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                })();'''

                # Initial popup cleanup pass
                if self.aggressive_popup:
                    try:
                        await page.evaluate(popup_cleanup_js)
                        if progress_callback:
                            progress_callback('🧹 Initial popup/overlay cleanup executed')
                    except Exception:
                        pass
                
                # Perform infinite scroll to load more content
                if progress_callback:
                    progress_callback(f"Scrolling page to load dynamic content ({scroll_count} scrolls)...")
                
                previous_height = 0
                no_change_count = 0
                images_before = len(media_urls)
                
                for i in range(scroll_count):
                    try:
                        # Get current scroll height
                        current_height = await page.evaluate('document.body.scrollHeight')
                        
                        # Count total images/videos on page
                        element_count = await page.evaluate('''
                            document.querySelectorAll('img, video, source').length
                        ''')
                        
                        # Check if page has grown (new content loaded)
                        if current_height == previous_height:
                            no_change_count += 1
                            # Stop if height hasn't changed for 5 consecutive scrolls
                            if no_change_count >= 5:
                                if progress_callback:
                                    progress_callback(f"✓ Reached end of content after {i + 1} scrolls ({element_count} media elements found)")
                                break
                        else:
                            no_change_count = 0
                        
                        previous_height = current_height
                        
                        # Scroll to bottom aggressively
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        
                        # Also try scrolling by a large amount in case scrollHeight doesn't update
                        await page.evaluate('window.scrollBy(0, 10000)')
                        
                        # Wait for new content to load (shorter wait for faster scrolling)
                        await page.wait_for_timeout(1500)

                        # Cleanup popups every scroll iteration (in case new ones appear)
                        if self.aggressive_popup:
                            try:
                                await page.evaluate(popup_cleanup_js)
                                if (i + 1) % 5 == 0 and progress_callback:
                                    progress_callback('🧹 Periodic popup cleanup performed')
                            except Exception:
                                pass
                        
                        # Progress update every 3 scrolls
                        if progress_callback and (i + 1) % 3 == 0:
                            new_media = len(media_urls) - images_before
                            progress_callback(f"Scroll {i + 1}/{scroll_count}: Found {element_count} elements, {len(media_urls)} media URLs (+{new_media} since start)")
                            images_before = len(media_urls)
                    
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Error during scroll {i + 1}: {str(e)[:50]}")
                        continue
                
                # Scroll back to top to ensure all content is in viewport
                try:
                    await page.evaluate('window.scrollTo(0, 0)')
                    await page.wait_for_timeout(500)
                except:
                    pass
                
                # Attempt to trigger video playback to force media requests
                try:
                    if progress_callback:
                        progress_callback("Triggering video playback to capture media streams...")
                    await page.evaluate('''
                        () => {
                            const clickElements = [];
                            document.querySelectorAll('video').forEach(v => {
                                try {
                                    v.muted = true;
                                    v.playsInline = true;
                                    if (v.paused) {
                                        const playPromise = v.play();
                                        if (playPromise) {
                                            playPromise.catch(() => {});
                                        }
                                    }
                                } catch (err) {}
                            });
                            document.querySelectorAll('[data-play], [data-video-play], .video-play, .playbutton, .play-button, button[class*="play"], a[class*="play"]').forEach(el => {
                                try { el.click(); } catch (err) {}
                            });
                        }
                    ''')
                    # Give the page MORE time to load video sources after interaction
                    await page.wait_for_timeout(3000)
                    # Aggressive cleanup after triggering playback (popups sometimes reappear)
                    if self.aggressive_popup:
                        try:
                            await page.evaluate(popup_cleanup_js)
                            if progress_callback:
                                progress_callback('🧹 Post-playback popup cleanup performed')
                        except Exception:
                            pass
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Video playback trigger failed: {str(e)[:80]}")

                # Extract media URLs from DOM elements after all scrolling
                if progress_callback:
                    # Final aggressive cleanup right before DOM scraping to ensure unobstructed access
                    if self.aggressive_popup:
                        try:
                            await page.evaluate(popup_cleanup_js)
                            progress_callback('🧹 Final popup cleanup before DOM extraction')
                        except Exception:
                            pass
                    progress_callback("Extracting media URLs from page elements...")
                
                try:
                    # Extract all media sources from the DOM (videos AND images)
                    dom_media = await page.evaluate(r'''
                        () => {
                            const media = new Set();
                            
                            // Get image elements (including lazy-loaded)
                            document.querySelectorAll('img').forEach(img => {
                                // Check src and all data attributes
                                if (img.src && img.src.startsWith('http')) media.add(img.src);
                                if (img.currentSrc && img.currentSrc.startsWith('http')) media.add(img.currentSrc);
                                
                                // Common lazy-load attributes
                                ['data-src', 'data-original', 'data-lazy-src', 'data-image', 'data-img', 
                                 'data-url', 'data-full', 'data-large', 'data-original-src'].forEach(attr => {
                                    const val = img.getAttribute(attr);
                                    if (val && val.startsWith('http')) {
                                        media.add(val);
                                    }
                                });
                            });
                            
                            // Get video elements
                            document.querySelectorAll('video').forEach(v => {
                                if (v.src) videos.add(v.src);
                                if (v.currentSrc) videos.add(v.currentSrc);
                                
                                // Check data attributes for video URLs (comprehensive list)
                                ['data-src', 'data-video', 'data-video-url', 'data-mp4', 'data-url', 
                                 'data-video-src', 'data-mediaurl', 'data-file', 'data-video-file',
                                 'data-quality-720p', 'data-quality-1080p', 'data-quality-480p'].forEach(attr => {
                                    const val = v.getAttribute(attr);
                                    if (val && (val.includes('.mp4') || val.includes('.webm') || val.includes('video') || val.includes('.m3u8'))) {
                                        videos.add(val);
                                    }
                                });
                                
                                // Check all attributes for video patterns
                                for (let attr of v.attributes) {
                                    if (attr.value && attr.value.match(/\.(mp4|webm|m3u8|mov)/i)) {
                                        videos.add(attr.value);
                                    }
                                }
                            });
                            
                            // Get source elements (inside video tags)
                            document.querySelectorAll('source').forEach(s => {
                                if (s.src) {
                                    if (s.type && s.type.startsWith('video')) {
                                        videos.add(s.src);
                                    } else if (s.src.match(/\.(mp4|webm|m3u8|mov)/i)) {
                                        videos.add(s.src);
                                    }
                                }
                            });
                            
                            // Check for video links in anchors
                            document.querySelectorAll('a').forEach(a => {
                                if (a.href && a.href.match(/\.(mp4|webm|mov|avi|mkv)/i)) {
                                    videos.add(a.href);
                                }
                            });
                            
                            // Look for download buttons or links
                            document.querySelectorAll('[href*="download"], [data-download], button[class*="download"]').forEach(el => {
                                const href = el.getAttribute('href') || el.getAttribute('data-download') || el.getAttribute('data-url');
                                if (href && href.match(/\.(mp4|webm|mov)/i)) {
                                    videos.add(href);
                                }
                            });
                            
                            // Search for media URLs in script tags (JSON data)
                            document.querySelectorAll('script').forEach(script => {
                                const text = script.textContent || '';
                                // Look for image URLs in JSON/script data
                                const imgMatches = text.match(/https?:\/\/[^\s"']+?\.(jpg|jpeg|png|gif|webp)/gi);
                                if (imgMatches) {
                                    imgMatches.forEach(url => media.add(url));
                                }
                                // Look for video URLs
                                const vidMatches = text.match(/https?:\/\/[^\s"']+?\.(mp4|webm|m3u8|mov)/gi);
                                if (vidMatches) {
                                    vidMatches.forEach(url => media.add(url));
                                }
                            });
                            
                            return Array.from(media);
                        }
                    ''')
                    
                    # Add DOM-extracted media to our sets (filter small thumbnails)
                    thumbnail_patterns = ['thumb', 'preview', 'screenshot', '/t/', 'thumbnail', 'thumbnails', '_thumb', '-thumb']
                    small_image_patterns = ['/thumb', '/t/', '_thumb', '-thumb', '_small', '-small', '/small/']
                    filtered_count = 0
                    image_count = 0
                    video_count = 0
                    
                    for media_url in dom_media:
                        if media_url:
                            lower_url = media_url.lower()
                            # Skip obvious small thumbnails (but keep larger preview images that might be full res)
                            if any(pattern in lower_url for pattern in small_image_patterns):
                                filtered_count += 1
                                continue
                            
                            # Categorize
                            if self._is_image_url(media_url):
                                image_count += 1
                            elif any(ext in lower_url for ext in ['.mp4', '.webm', '.m3u8', '.mov']):
                                video_count += 1
                            
                            media_urls.add(media_url)
                    
                    if progress_callback and dom_media:
                        progress_callback(f"✓ Extracted {len(dom_media)} URLs from DOM ({image_count} images, {video_count} videos, {filtered_count} thumbnails filtered)")
                
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Warning: DOM media extraction failed: {str(e)[:100]}")
                
                # Get final HTML with all loaded content
                content = await page.content()
                
                if progress_callback:
                    final_count = await page.evaluate('document.querySelectorAll("img, video, source").length')
                    progress_callback(f"✅ Rendering complete: {final_count} media elements, {len(media_urls)} URLs captured via network")
                
                try:
                    await browser.close()
                except Exception:
                    pass  # Suppress cleanup errors
                
                return content, media_urls
        except ImportError:
            if progress_callback:
                progress_callback("⚠️ Playwright not installed - using basic scraping (will miss dynamic content)")
            return None, set()
        except Exception as e:
            if progress_callback:
                progress_callback(f"❌ Playwright error: {str(e)[:200]} - falling back to basic scraping")
            return None, set()

    def _resolve_with_playwright(self, url, progress_callback=None, timeout=30000):
        """Use Playwright to open the URL and capture any video/large-binary responses.

        Returns the first candidate response URL (or None).
        """
        try:
            from playwright.sync_api import sync_playwright

            if progress_callback:
                progress_callback(f"Using Playwright to resolve download link: {url}")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                candidate = None

                def handle_response(response):
                    nonlocal candidate
                    try:
                        headers = response.headers
                        ctype = headers.get('content-type', '').lower()
                        clen = int(headers.get('content-length') or 0)
                        rurl = response.url
                        # Prefer explicit video content-types or large responses
                        if ctype.startswith('video/') or 'application/octet-stream' in ctype or clen > 500000 or rurl.lower().endswith(('.mp4', '.webm', '.mov', '.flv')):
                            if not candidate:
                                candidate = rurl
                    except Exception:
                        pass

                page.on('response', handle_response)

                try:
                    resp = page.goto(url, wait_until='networkidle', timeout=timeout)
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Playwright navigation error: {str(e)[:120]}")
                # Wait a little for any lazy-loaded responses
                page.wait_for_timeout(2000)

                # If candidate found, return it
                if candidate:
                    if progress_callback:
                        progress_callback(f"Playwright found candidate media URL: {candidate}")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    return candidate

                # As a last resort, inspect all responses captured by the page
                # (playwright keeps them accessible via page.responses in sync API)
                try:
                    # Note: page.responses is not in official API but may exist in some contexts
                    for r in getattr(page, 'responses', []):  # type: ignore
                        try:
                            headers = r.headers
                            ctype = headers.get('content-type', '').lower()
                            clen = int(headers.get('content-length') or 0)
                            rurl = r.url
                            if ctype.startswith('video/') or clen > 500000 or rurl.lower().endswith(('.mp4', '.webm', '.mov', '.flv')):
                                try:
                                    browser.close()
                                except Exception:
                                    pass
                                if progress_callback:
                                    progress_callback(f"Playwright fallback found media URL: {rurl}")
                                return rurl
                        except Exception:
                            continue
                except Exception:
                    pass

                try:
                    browser.close()
                except Exception:
                    pass
        except ImportError:
            if progress_callback:
                progress_callback("Playwright sync API not available - skipping playwright resolution")
            return None
        except Exception as e:
            if progress_callback:
                progress_callback(f"Playwright resolver error: {str(e)[:200]}")
        return None
    
    def scrape_page(
        self,
        url,
        base_path,
        progress_callback=None,
        custom_name=None,
        max_pages=10,
        scroll_count=5,
        collect_only=False,
    ):
        """Scrape media from web pages with JavaScript rendering support and pagination
        
        Args:
            url: Starting URL to scrape
            base_path: Base download directory
            progress_callback: Function to call with progress updates
            custom_name: Custom folder name for downloads
            max_pages: Maximum number of pages to follow (default 10)
            scroll_count: Number of scrolls for infinite scroll sites (default 5)
        """
        all_results = []
        visited_urls = set()
        current_url = url
        page_count = 0
        
        while current_url and page_count < max_pages:
            if current_url in visited_urls:
                break  # Avoid infinite loops
            
            visited_urls.add(current_url)
            page_count += 1
            
            if progress_callback:
                progress_callback(f"Scraping page {page_count}/{max_pages}: {current_url}")
            
            # Scrape current page
            page_results = self._scrape_single_page(
                current_url,
                base_path,
                progress_callback,
                custom_name,
                scroll_count,
                collect_only=collect_only,
            )
            all_results.extend(page_results)
            
            # Try to find next page link
            next_url = self._find_next_page_link(current_url, progress_callback)
            current_url = next_url
            
            if not next_url:
                if progress_callback:
                    progress_callback(f"No more pages found. Scraped {page_count} page(s) total.")
                break
        
        if progress_callback and not collect_only:
            progress_callback(f"Completed pagination: {len(all_results)} total files from {page_count} page(s)")

        return all_results
    
    def _scrape_single_page(
        self,
        url,
        base_path,
        progress_callback=None,
        custom_name=None,
        scroll_count=5,
        collect_only=False,
        seen_pairs=None,
    ):
        """Scrape media from a single web page."""
        downloaded: List[str] = []
        collected: List[Dict] = []
        new_media = 0
        skipped_media = 0
        seen_pairs = seen_pairs or set()

        def should_skip(history_url: str) -> bool:
            if self.history.is_website_url_downloaded(url, history_url):
                return True
            key = (history_url, url)
            if key in seen_pairs:
                return True
            seen_pairs.add(key)
            return False

        def queue_candidate(media_url: str, download_path: str, force_video: bool = True, history_url: Optional[str] = None, force_yt_dlp: bool = False):
            entry = {
                'source_page': url,
                'media_url': media_url,
                'download_path': download_path,
                'force_video': force_video,
                'history_url': history_url or media_url,
                'force_yt_dlp': force_yt_dlp,
            }
            collected.append(entry)
        
        try:
            # Create folder name from custom name or domain
            if custom_name:
                folder_name = sanitize_filename(custom_name)
            else:
                domain = urlparse(url).netloc.replace('www.', '')
                folder_name = sanitize_filename(domain)
            from .utils import build_download_subfolder
            download_path = ensure_download_directory(base_path, build_download_subfolder('website', folder_name))
            
            if progress_callback:
                progress_callback(f"Fetching page: {url}")
            
            # Force Playwright for sites that require JavaScript (thothub.to, etc.)
            force_playwright = 'thothub.to' in url.lower()
            
            if progress_callback and force_playwright:
                progress_callback(f"🔍 thothub.to detected - using Playwright to extract media...")
            
            # Try Playwright rendering for JavaScript-heavy sites with infinite scroll
            playwright_content = None
            playwright_media = set()
            try:
                playwright_content, playwright_media = asyncio.run(self._render_page_with_playwright(url, progress_callback, scroll_count))
                if progress_callback:
                    if playwright_media:
                        progress_callback(f"✓ Playwright found {len(playwright_media)} media URL(s)")
                        # Show first few URLs for debugging
                        for idx, media in enumerate(list(playwright_media)[:3], 1):
                            progress_callback(f"  {idx}. {media[:100]}...")
                    elif force_playwright:
                        progress_callback(f"⚠ Playwright ran but found NO media on thothub.to page")
            except Exception as e:
                if progress_callback:
                    error_msg = f"Playwright render failed: {str(e)[:120]}"
                    if force_playwright:
                        progress_callback(f"❌ {error_msg} - thothub.to requires Playwright!")
                        progress_callback(f"💡 Make sure Playwright is installed: playwright install")
                        # Don't continue if Playwright is required
                        return collected if collect_only else downloaded
                    progress_callback(error_msg + ", using fallback")
            
            # Use Playwright content if available, otherwise fall back to requests
            if playwright_content:
                soup = BeautifulSoup(playwright_content, 'html.parser')
                page_text = playwright_content
            else:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                page_text = response.text
            
            # Download media URLs found by Playwright
            for media_url in playwright_media:
                if should_skip(media_url):
                    skipped_media += 1
                    continue

                # Determine if this is likely a video based on URL patterns
                is_video = any(ext in media_url.lower() for ext in ['.mp4', '.webm', '.m3u8', '.mov', '.avi', '.mkv'])
                media_type = "video" if is_video else "media"

                if collect_only:
                    queue_candidate(media_url, download_path, force_video=is_video)
                    continue

                if progress_callback:
                    progress_callback(f"Downloading {media_type} from JS rendering: {media_url[:80]}...")

                target_dir, kind = self._media_subdir_for(media_url, download_path, force_video=is_video)
                filepath = self._download_with_fallback(media_url, target_dir, source_url=url, progress_callback=progress_callback)
                if filepath:
                    downloaded.append(filepath)
                    new_media += 1
                    if progress_callback:
                        # Report file size to help identify thumbnails
                        import os
                        if os.path.exists(filepath):
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            progress_callback(f"✓ Saved {media_type}: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                self._record_history(url, media_url, filepath)

            # Extract video URLs embedded directly in page text (JSON, scripts, etc.)
            if page_text:
                # Find URLs with typical video extensions
                text_video_urls = set()
                escaped_pattern = re.compile(r'https?:\\/\\/[^"\'\s<>]+?\.(?:mp4|webm|m3u8|mov|avi|mkv)(?:\?[^"\'\s<>]*)?', re.IGNORECASE)
                raw_matches = list(escaped_pattern.findall(page_text))

                # Regex for non-escaped URLs
                pattern_plain = re.compile(r'https?://[^"\'\s<>]+?\.(?:mp4|webm|m3u8|mov|avi|mkv)(?:\?[^"\'\s<>]*)?', re.IGNORECASE)
                raw_matches.extend(pattern_plain.findall(page_text))

                for match in raw_matches:
                    cleaned = match.replace(r'\/', '/').replace(r'\u0026', '&').replace(r'\/', '/').strip()
                    if cleaned.startswith('http'):
                        text_video_urls.add(cleaned)

                if text_video_urls:
                    if progress_callback:
                        progress_callback(f"Found {len(text_video_urls)} potential video URLs embedded in page text")

                for media_url in text_video_urls:
                    if any(pattern in media_url.lower() for pattern in ['thumb', 'preview', 'poster', 'screenshot', '_thumb']) and self._is_image_url(media_url):
                        continue
                    if should_skip(media_url):
                        skipped_media += 1
                        continue

                    if collect_only:
                        queue_candidate(media_url, download_path, force_video=True)
                        continue

                    if progress_callback:
                        progress_callback(f"Downloading video from page text: {media_url[:80]}...")

                    target_dir, kind = self._media_subdir_for(media_url, download_path, force_video=True)
                    filepath = self._download_with_fallback(media_url, target_dir, source_url=url, progress_callback=progress_callback)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                        if progress_callback and os.path.exists(filepath):
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            progress_callback(f"✓ Saved video from text: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                    self._record_history(url, media_url, filepath)
            
            # For Wayback archived pages, look for direct archived video files (not download wrappers)
            if 'web.archive.org' in url:
                # Find archived video files directly in the HTML (e.g., wp-content/uploads/*.avi)
                archived_video_pattern = re.compile(r'(https?://web\.archive\.org/web/\d+im_/[^"\'>\s]+\.(?:avi|mp4|flv|mov|webm))', re.IGNORECASE)
                archived_videos = set(archived_video_pattern.findall(page_text))
                for video_url in archived_videos:
                    # Skip thumbnails
                    if video_url.lower().endswith('.jpg') or video_url.lower().endswith('.png'):
                        continue
                    if should_skip(video_url):
                        skipped_media += 1
                        continue
                    if collect_only:
                        queue_candidate(video_url, download_path, force_video=True, force_yt_dlp=True)
                        continue
                    if progress_callback:
                        progress_callback(f"Found archived video file: {video_url[:80]}...")
                    target_dir, kind = self._media_subdir_for(video_url, download_path, force_video=True)
                    filepath = self._download_with_fallback(video_url, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                        if progress_callback and os.path.exists(filepath):
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            progress_callback(f"✓ Saved archived video: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                    self._record_history(url, video_url, filepath)
            
            # Find all video tags (including source elements)
            video_tags = soup.find_all(['video', 'source'])
            if progress_callback:
                if video_tags:
                    progress_callback(f"Found {len(video_tags)} <video>/<source> tags on page")
                else:
                    progress_callback(f"No <video> tags found on page")
            
            for video_tag in video_tags:
                video_src = video_tag.get('src')
                if video_src:
                    full_url = urljoin(url, str(video_src))
                    if should_skip(full_url):
                        skipped_media += 1
                        continue
                    
                    if collect_only:
                        queue_candidate(full_url, download_path, force_video=True)
                        continue
                    
                    if progress_callback:
                        progress_callback(f"Downloading video from <video> tag: {full_url[:80]}...")
                    
                    target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                    filepath = self._download_with_fallback(full_url, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                        if progress_callback and os.path.exists(filepath):
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            progress_callback(f"✓ Saved video from <video> tag: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                    self._record_history(url, full_url, filepath)
            
            # Find all iframes that might contain videos
            all_iframes = soup.find_all('iframe')
            video_iframes = []
            for iframe in all_iframes:
                iframe_src = iframe.get('src') or iframe.get('data-src')
                if iframe_src:
                    full_url = urljoin(url, str(iframe_src))
                    # Common video player domains
                    if any(domain in full_url.lower() for domain in ['youtube.com', 'vimeo.com', 'dailymotion.com', 'streamable.com', 'player.', 'embed']):
                        video_iframes.append((iframe, full_url))
            
            if progress_callback:
                if video_iframes:
                    progress_callback(f"Found {len(video_iframes)} video iframe(s) on page")
                else:
                    progress_callback(f"No video iframes found on page")
            
            for iframe, full_url in video_iframes:
                if should_skip(full_url):
                    skipped_media += 1
                    continue
                
                if collect_only:
                    queue_candidate(full_url, download_path, force_video=True, force_yt_dlp=True)
                    continue
                
                if progress_callback:
                    progress_callback(f"Downloading video from iframe embed: {full_url[:80]}...")
                
                target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                filepath = self._download_with_fallback(full_url, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                if filepath:
                    downloaded.append(filepath)
                    new_media += 1
                    if progress_callback and os.path.exists(filepath):
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        progress_callback(f"✓ Saved video from iframe: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                self._record_history(url, full_url, filepath)
            
            # Find all images
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    full_url = urljoin(url, str(src))
                    # Check if already downloaded
                    if should_skip(full_url):
                        skipped_media += 1
                        continue
                    if collect_only:
                        continue
                    
                    target_dir, kind = self._media_subdir_for(full_url, download_path)
                    filepath = self._download_with_fallback(full_url, target_dir, source_url=url)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                    # Mark as seen even if download failed (include sha if we downloaded)
                    self._record_history(url, full_url, filepath)

            # Detect direct download links like file.php?dl=ID (Stickaps / StickamVids)
            for a in soup.find_all('a', href=True):
                href = str(a['href'])
                if 'file.php?dl=' in href or re.search(r'/file\.php\?dl=\w+', href):
                    download_link = urljoin(url, href)
                    # Avoid duplicates
                    if should_skip(download_link):
                        continue

                    if progress_callback:
                        progress_callback(f"Found direct download link: {download_link}")

                    # Attempt to resolve redirect and download
                    try:
                        head = self.session.head(download_link, allow_redirects=True, timeout=20)
                        head.raise_for_status()
                        final_url = head.url
                        content_type = head.headers.get('content-type', '').lower()
                        content_length = head.headers.get('content-length')
                        if progress_callback:
                            progress_callback(f"Resolved download link -> {final_url} (type={content_type}, len={content_length})")
                    except Exception:
                        # Fallback to GET if HEAD fails
                        try:
                            resp = self.session.get(download_link, allow_redirects=True, timeout=30, stream=True)
                            resp.raise_for_status()
                            final_url = resp.url
                            content_type = resp.headers.get('content-type', '').lower()
                            content_length = resp.headers.get('content-length')
                            if progress_callback:
                                progress_callback(f"Resolved (GET) download link -> {final_url} (type={content_type}, len={content_length})")
                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"Failed to fetch download link {download_link}: {str(e)[:120]}")
                            # continue on and still attempt Playwright resolution below
                            final_url = None
                            content_type = ''
                            content_length = None

                    # For Wayback archived links, try to extract the actual archived media URL
                    wayback_video_url = None
                    if 'web.archive.org' in download_link:
                        try:
                            # Fetch the wayback page and look for video/media URLs in the archived content
                            resp = self.session.get(download_link, timeout=30)
                            if resp.status_code == 200:
                                # Try to extract an archived video URL from the page
                                # Look for typical video file patterns in wayback archived pages
                                video_patterns = [
                                    r'(https?://web\.archive\.org/web/\d+im_/[^"\'>\s]+\.(?:mp4|flv|avi|mov|webm))',
                                    r'(https?://web\.archive\.org/web/\d+/[^"\'>\s]+\.(?:mp4|flv|avi|mov|webm))',
                                    r'(https?://[^"\'>\s]+\.(?:mp4|webm|m3u8|mov|avi|mkv))',
                                ]
                                for pat in video_patterns:
                                    matches = re.findall(pat, resp.text, re.IGNORECASE)
                                    if matches:
                                        wayback_video_url = matches[0]
                                        if progress_callback:
                                            progress_callback(f"Found archived video URL by regex: {wayback_video_url}")
                                        break
                                # Aggressively parse for <video> and <source> tags
                                soup2 = BeautifulSoup(resp.text, 'html.parser')
                                for video_tag in soup2.find_all('video'):
                                    src = video_tag.get('src')
                                    if src:
                                        src_str = str(src)
                                        if src_str.startswith('http') and src_str.lower().endswith(('.mp4','.webm','.m3u8','.mov','.avi','.mkv')):
                                            wayback_video_url = src_str
                                            if progress_callback:
                                                progress_callback(f"Found <video> src: {wayback_video_url}")
                                            break
                                    for source_tag in video_tag.find_all('source'):
                                        src2 = source_tag.get('src')
                                        if src2:
                                            src2_str = str(src2)
                                            if src2_str.startswith('http') and src2_str.lower().endswith(('.mp4','.webm','.m3u8','.mov','.avi','.mkv')):
                                                wayback_video_url = src2_str
                                                if progress_callback:
                                                    progress_callback(f"Found <source> src: {wayback_video_url}")
                                                break
                                # Check <a> tags for direct video links
                                if not wayback_video_url:
                                    for a_tag in soup2.find_all('a', href=True):
                                        href = str(a_tag['href'])
                                        if href.startswith('http') and href.lower().endswith(('.mp4','.webm','.m3u8','.mov','.avi','.mkv')):
                                            wayback_video_url = href
                                            if progress_callback:
                                                progress_callback(f"Found <a> video link: {wayback_video_url}")
                                            break
                                # Check for iframe and follow its src
                                if not wayback_video_url:
                                    for iframe_tag in soup2.find_all('iframe', src=True):
                                        iframe_src = str(iframe_tag['src'])
                                        if iframe_src.startswith('http'):
                                            if progress_callback:
                                                progress_callback(f"Found iframe src: {iframe_src}, following for video links...")
                                            try:
                                                iframe_resp = self.session.get(iframe_src, timeout=30)
                                                if iframe_resp.status_code == 200:
                                                    # Try to extract video URLs from iframe page
                                                    iframe_patterns = [
                                                        r'(https?://[^"\'>\s]+\.(?:mp4|webm|m3u8|mov|avi|mkv))',
                                                    ]
                                                    for pat in iframe_patterns:
                                                        matches = re.findall(pat, iframe_resp.text, re.IGNORECASE)
                                                        if matches:
                                                            wayback_video_url = matches[0]
                                                            if progress_callback:
                                                                progress_callback(f"Found video URL in iframe: {wayback_video_url}")
                                                            break
                                                    # Also check for <video> and <source> tags in iframe
                                                    soup_iframe = BeautifulSoup(iframe_resp.text, 'html.parser')
                                                    for video_tag in soup_iframe.find_all('video'):
                                                        src = video_tag.get('src')
                                                        if src:
                                                            src_str = str(src)
                                                            if src_str.startswith('http') and src_str.lower().endswith(('.mp4','.webm','.m3u8','.mov','.avi','.mkv')):
                                                                wayback_video_url = src_str
                                                                if progress_callback:
                                                                    progress_callback(f"Found <video> src in iframe: {wayback_video_url}")
                                                                break
                                                        for source_tag in video_tag.find_all('source'):
                                                            src2 = source_tag.get('src')
                                                            if src2:
                                                                src2_str = str(src2)
                                                                if src2_str.startswith('http') and src2_str.lower().endswith(('.mp4','.webm','.m3u8','.mov','.avi','.mkv')):
                                                                    wayback_video_url = src2_str
                                                                    if progress_callback:
                                                                        progress_callback(f"Found <source> src in iframe: {wayback_video_url}")
                                                                    break
                                            except Exception as e:
                                                if progress_callback:
                                                    progress_callback(f"Failed to fetch iframe src: {iframe_src} ({e})")
                        except Exception:
                            pass
                    
                    if wayback_video_url:
                        if collect_only:
                            queue_candidate(wayback_video_url, download_path, force_video=True, history_url=download_link, force_yt_dlp=True)
                            continue
                        # Try downloading the extracted Wayback video URL
                        target_dir, kind = self._media_subdir_for(wayback_video_url, download_path, force_video=True)
                        filepath = self._download_with_fallback(wayback_video_url, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                        if filepath:
                            downloaded.append(filepath)
                            new_media += 1
                            if progress_callback:
                                import os
                                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                                progress_callback(f"✓ Saved Wayback archived video: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                            self._record_history(url, download_link, filepath)
                            continue
                    
                    # Always attempt Playwright resolver on the original download link to capture browser-only responses
                    try:
                        if progress_callback:
                            progress_callback("Running Playwright resolver for download link (always)...")
                        candidate = self._resolve_with_playwright(download_link, progress_callback)
                        if candidate:
                            if collect_only:
                                queue_candidate(candidate, download_path, force_video=True, history_url=download_link, force_yt_dlp=True)
                                continue
                            if progress_callback:
                                progress_callback(f"Playwright resolver returned candidate: {candidate}")
                            # Try downloading the candidate (force yt-dlp)
                            target_dir, kind = self._media_subdir_for(candidate, download_path, force_video=True)
                            filepath = self._download_with_fallback(candidate, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                            if filepath:
                                downloaded.append(filepath)
                                new_media += 1
                                if progress_callback:
                                    import os
                                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                                    progress_callback(f"✓ Saved Playwright-resolved file: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                                self._record_history(url, download_link, filepath)
                                continue
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Playwright resolver error (ignored): {str(e)[:120]}")

                    # If content type looks like video or large binary, download with fallback
                    # If content type looks like video or large binary, download with fallback
                    force_dl = False
                    if 'video' in content_type or 'application/octet-stream' in content_type or (final_url and final_url.lower().endswith(('.mp4', '.webm', '.mov', '.flv'))):
                        force_dl = True

                    # If resolved content is an image and very small, try forcing yt-dlp on original download link
                    if content_type and content_type.startswith('image'):
                        try:
                            size = int(content_length) if content_length else 0
                        except:
                            size = 0
                        if size < 300000:  # likely a thumbnail; force yt-dlp
                            if progress_callback:
                                progress_callback(f"Resolved file is an image ({size} bytes) — trying yt-dlp on the file.php link as fallback")
                            if collect_only:
                                queue_candidate(download_link, download_path, force_video=True, history_url=download_link, force_yt_dlp=True)
                                continue
                            target_dir, kind = self._media_subdir_for(download_link, download_path, force_video=True)
                            filepath = self._download_with_fallback(download_link, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                            if filepath:
                                downloaded.append(filepath)
                                new_media += 1
                                if progress_callback:
                                    import os
                                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                                    progress_callback(f"✓ Saved downloaded file.php video (yt-dlp): {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                                    self._record_history(url, download_link, filepath)
                                    continue
                                else:
                                    # yt-dlp didn't succeed — try Playwright to capture the actual media response
                                    if progress_callback:
                                        progress_callback("yt-dlp did not extract a video; attempting Playwright resolver...")
                                    try:
                                        candidate = None
                                        try:
                                            candidate = self._resolve_with_playwright(download_link, progress_callback)
                                        except Exception as e:
                                            if progress_callback:
                                                progress_callback(f"Playwright resolver failed: {str(e)[:120]}")

                                        if candidate:
                                            if progress_callback:
                                                progress_callback(f"Playwright returned candidate media URL: {candidate}")
                                            target_dir, kind = self._media_subdir_for(candidate, download_path, force_video=True)
                                            fp = self._download_with_fallback(candidate, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                                            if fp:
                                                downloaded.append(fp)
                                                new_media += 1
                                                if progress_callback:
                                                    import os
                                                    size_mb = os.path.getsize(fp) / (1024 * 1024)
                                                    progress_callback(f"✓ Saved video from Playwright candidate: {os.path.basename(fp)} ({size_mb:.2f} MB)")
                                                self._record_history(url, download_link, filepath)
                                                continue
                                    except Exception:
                                        pass
                                    # If still nothing, do NOT mark as seen so it can retry on next run
                                    continue

                    if force_dl:
                        if collect_only:
                            queue_candidate(final_url or download_link, download_path, force_video=True, history_url=download_link, force_yt_dlp=True)
                            continue
                        # Use _download_with_fallback to handle redirects and yt-dlp (force yt-dlp for file.php links)
                        target_dir, kind = self._media_subdir_for(final_url or download_link, download_path, force_video=True)
                        filepath = self._download_with_fallback(final_url or download_link, target_dir, source_url=url, progress_callback=progress_callback, force_yt_dlp=True)
                        if filepath:
                            downloaded.append(filepath)
                            new_media += 1
                            if progress_callback:
                                import os
                                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                                progress_callback(f"✓ Saved downloaded file.php video: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                            self._record_history(url, download_link, filepath)
            
            # Find all videos
            for video in soup.find_all('video'):
                # Check video src attribute
                src = video.get('src') or video.get('data-src')
                if src:
                    full_url = urljoin(url, str(src))
                    if should_skip(full_url):
                        skipped_media += 1
                        continue
                    if collect_only:
                        queue_candidate(full_url, download_path, force_video=True)
                        continue
                    
                    target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                    filepath = self._download_with_fallback(full_url, target_dir, source_url=url, progress_callback=progress_callback)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                    self._record_history(url, full_url, filepath)
                
                # Check source tags within video
                for source in video.find_all('source'):
                    src = source.get('src') or source.get('data-src')
                    if src:
                        full_url = urljoin(url, str(src))
                        if should_skip(full_url):
                            skipped_media += 1
                            continue
                        if collect_only:
                            queue_candidate(full_url, download_path, force_video=True)
                            continue
                        
                        target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                        filepath = self._download_with_fallback(full_url, target_dir, source_url=url, progress_callback=progress_callback)
                        if filepath:
                            downloaded.append(filepath)
                            new_media += 1
                        self._record_history(url, full_url, filepath)
                
                # Check for data attributes commonly used for videos
                for attr in ['data-video-src', 'data-mp4', 'data-webm']:
                    src = video.get(attr)
                    if src:
                        full_url = urljoin(url, str(src))
                        if should_skip(full_url):
                            skipped_media += 1
                            continue
                        if collect_only:
                            queue_candidate(full_url, download_path, force_video=True)
                            continue
                        
                        target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                        filepath = self._download_with_fallback(full_url, target_dir, source_url=url, progress_callback=progress_callback)
                        if filepath:
                            downloaded.append(filepath)
                            new_media += 1
                        self._record_history(url, full_url, filepath)
            
            # Look for video URLs in data attributes of other elements
            for element in soup.find_all(attrs={'data-video-url': True}):
                src = element.get('data-video-url')
                if src:
                    full_url = urljoin(url, str(src))
                    if should_skip(full_url):
                        skipped_media += 1
                        continue
                    if collect_only:
                        queue_candidate(full_url, download_path, force_video=True)
                        continue
                    
                    target_dir, kind = self._media_subdir_for(full_url, download_path, force_video=True)
                    filepath = self._download_with_fallback(full_url, target_dir, source_url=url)
                    if filepath:
                        downloaded.append(filepath)
                        new_media += 1
                    self._record_history(url, full_url, filepath)
            
            # Check for iframes with video embeds (YouTube, Vimeo, etc.)
            for iframe in soup.find_all('iframe'):
                iframe_src = iframe.get('src')
                if iframe_src:
                    # Try to extract video URL from common embed services
                    if 'youtube.com' in iframe_src or 'youtu.be' in iframe_src:
                        if progress_callback:
                            progress_callback(f"Found YouTube embed: {iframe_src}")
                    elif 'vimeo.com' in iframe_src:
                        if progress_callback:
                            progress_callback(f"Found Vimeo embed: {iframe_src}")
            
            # Scan page source for video URLs in JavaScript/JSON (common in modern sites)
            # page_text already set above from Playwright or requests
            # Look for common video URL patterns
            video_patterns = [
                r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*',
                r'https?://[^\s"\'<>]+\.webm[^\s"\'<>]*',
                r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
                r'https?://[^\s"\'<>]+/videos?/[^\s"\'<>]+',
                r'"video[Uu]rl":\s*"([^"]+)"',
                r'"[Ss]rc":\s*"(https?://[^"]+\.(mp4|webm))"',
            ]
            
            found_video_urls = set()
            for pattern in video_patterns:
                matches = re.findall(pattern, page_text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]  # Extract from group
                    if match and match.startswith('http'):
                        found_video_urls.add(match)
            
            # Download found video URLs
            for video_url in found_video_urls:
                # Clean up the URL (remove escape characters, etc.)
                video_url = video_url.replace('\\/', '/').replace('\\"', '"')
                
                if should_skip(video_url):
                    skipped_media += 1
                    continue
                if collect_only:
                    queue_candidate(video_url, download_path, force_video=True)
                    continue
                
                if progress_callback:
                    progress_callback(f"Found embedded video: {video_url[:80]}...")
                
                target_dir, kind = self._media_subdir_for(video_url, download_path, force_video=True)
                filepath = self._download_with_fallback(video_url, target_dir, source_url=url)
                if filepath:
                    downloaded.append(filepath)
                    new_media += 1
                self._record_history(url, video_url, filepath)
            
            # Find links to media files
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    full_url = urljoin(url, str(href))
                    if any(full_url.lower().endswith(ext) for ext in 
                          ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.mov']):
                        is_video = full_url.lower().endswith(('.mp4', '.webm', '.mov'))
                        if should_skip(full_url):
                            skipped_media += 1
                            continue
                        if collect_only:
                            if is_video:
                                queue_candidate(full_url, download_path, force_video=True)
                            continue
                        
                        target_dir, kind = self._media_subdir_for(full_url, download_path)
                        filepath = self._download_with_fallback(full_url, target_dir, source_url=url)
                        if filepath:
                            downloaded.append(filepath)
                            new_media += 1
                        self._record_history(url, full_url, filepath)
            
            if progress_callback:
                if new_media == 0 and skipped_media == 0:
                    # No media found at all - this might indicate a problem
                    progress_callback(f"⚠ {url}: No media found on this page")
                    if 'thothub.to' in url.lower():
                        progress_callback(f"  → thothub.to debugging info:")
                        # Show what we found on the page
                        video_tags = soup.find_all('video')
                        img_tags = soup.find_all('img')
                        source_tags = soup.find_all('source')
                        iframe_tags = soup.find_all('iframe')
                        progress_callback(f"     • Found {len(video_tags)} <video> tags, {len(source_tags)} <source> tags")
                        progress_callback(f"     • Found {len(img_tags)} <img> tags, {len(iframe_tags)} <iframe> tags")
                        progress_callback(f"     • Playwright found: {len(playwright_media)} media URLs")
                        progress_callback(f"     • Page may need special extraction logic or different rendering")
                else:
                    progress_callback(f"{url}: {new_media} new media, {skipped_media} already seen")

            # Save history after each page (only if we actually downloaded)
            if not collect_only:
                self.history.save_history()
        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error scraping page {url}: {str(e)}")

        return collected if collect_only else downloaded
    
    def _find_next_page_link(self, url, progress_callback=None):
        """Find the next page link for pagination
        
        Looks for common pagination patterns like:
        - Links with text: "Next", "Next Page", "→", "»"
        - Links with class: "next", "pagination-next"
        - Links with rel="next"
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple strategies to find next page link
            
            # Strategy 1: Look for rel="next" attribute
            next_link = soup.find('a', rel='next')
            if next_link and next_link.get('href'):
                next_url = urljoin(url, str(next_link['href']))
                if progress_callback:
                    progress_callback(f"Found next page (rel=next): {next_url}")
                return next_url
            
            # Strategy 2: Look for common text patterns
            next_patterns = ['next', 'next page', '→', '»', 'older', 'previous posts']
            for pattern in next_patterns:
                # Case-insensitive search
                for link in soup.find_all('a', href=True):
                    link_text = link.get_text(strip=True).lower()
                    if pattern in link_text:
                        next_url = urljoin(url, str(link['href']))
                        if progress_callback:
                            progress_callback(f"Found next page (text='{link_text}'): {next_url}")
                        return next_url
            
            # Strategy 3: Look for common class names
            class_patterns = ['next', 'pagination-next', 'pager-next', 'nav-next', 'next-page']
            for pattern in class_patterns:
                next_link = soup.find('a', class_=lambda c: bool(c and pattern in c.lower()) if isinstance(c, str) else False)
                if next_link and next_link.get('href'):
                    next_url = urljoin(url, str(next_link['href']))
                    if progress_callback:
                        progress_callback(f"Found next page (class): {next_url}")
                    return next_url
            
            # Strategy 4: Look for page numbers (find the current page and get the next one)
            current_page_num = None
            pagination_links = soup.find_all('a', class_=lambda c: bool(c and 'page' in str(c).lower()) if c else False)
            
            for link in pagination_links:
                link_text = link.get_text(strip=True)
                if link_text.isdigit():
                    page_num = int(link_text)
                    # Check if this is the current page (might have a different class or be a span)
                    if link.name == 'span' or 'current' in str(link.get('class', '')).lower():
                        current_page_num = page_num
            
            # If we found the current page number, look for the next one
            if current_page_num:
                for link in pagination_links:
                    link_text = link.get_text(strip=True)
                    if link_text.isdigit() and int(link_text) == current_page_num + 1:
                        next_url = urljoin(url, str(link['href']))
                        if progress_callback:
                            progress_callback(f"Found next page (page {current_page_num + 1}): {next_url}")
                        return next_url
            
            # No next page found
            return None
            
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error finding next page: {str(e)}")
            return None
    
    def process_download_queue(
        self,
        queue: DownloadQueue,
        progress_callback=None,
        pause_checker=None,
        progress_hook=None,
    ) -> List[str]:
        """Download all pending items stored in a DownloadQueue with concurrent processing."""
        downloaded: List[str] = []
        processed = 0
        
        # Collect all items first
        all_items = []
        while True:
            item = queue.pop_next()
            if not item:
                break
            all_items.append(item)
        
        if not all_items:
            return downloaded
        
        if progress_callback:
            progress_callback(f"Starting concurrent download of {len(all_items)} items using {self.max_workers} workers")
        
        def download_item(item):
            """Download a single item with retry logic"""
            media_url = item.get('media_url')
            source_page = item.get('source_page') or media_url
            download_path = item.get('download_path') or ensure_download_directory('Downloads', 'unsorted')
            force_video = bool(item.get('force_video', True))
            history_url = item.get('history_url') or media_url
            force_yt_dlp = bool(item.get('force_yt_dlp', False))
            
            # Skip if already downloaded
            if self.history.is_website_url_downloaded(source_page, history_url):
                return None, "skipped"
            
            target_dir, kind = self._media_subdir_for(media_url, download_path, force_video=force_video)
            
            # Retry logic with exponential backoff
            max_retries = 3
            last_error = None
            for attempt in range(max_retries):
                try:
                    # Create a simple callback that captures messages
                    messages = []
                    def capture_callback(msg):
                        messages.append(msg)
                    
                    filepath = self._download_with_fallback(
                        media_url,
                        target_dir,
                        source_url=source_page,
                        progress_callback=capture_callback,
                        force_yt_dlp=force_yt_dlp,
                    )
                    if filepath:
                        self._record_history(source_page, history_url, filepath)
                        return filepath, "success"
                    
                    # If no filepath and we have error messages, use them
                    if messages:
                        # Find the most relevant error message (prioritize HTTP errors)
                        error_msg = next((m for m in messages if 'HTTP' in m or 'Forbidden' in m or '404' in m or '403' in m), None)
                        if not error_msg:
                            error_msg = next((m for m in messages if 'error' in m.lower() or 'failed' in m.lower() or 'timeout' in m.lower()), None)
                        if error_msg:
                            last_error = error_msg.replace('❌ ', '').replace('✗ ', '')
                    
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    
                    return None, last_error if last_error else "failed (no response)"
                    
                except Exception as e:
                    last_error = f"exception: {str(e)[:80]}"
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    return None, last_error
            
            return None, last_error if last_error else "failed"
        
        # Process downloads concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(download_item, item): item for item in all_items}
            
            for future in as_completed(future_to_item):
                # Check pause
                if pause_checker:
                    notified = False
                    while pause_checker():
                        if progress_callback and not notified:
                            progress_callback("⏸ Paused - resume to continue downloads")
                            notified = True
                        time.sleep(0.5)
                    if notified and progress_callback:
                        progress_callback("▶ Resuming downloads...")
                
                item = future_to_item[future]
                media_url = item.get('media_url')
                
                try:
                    filepath, status = future.result()
                    if filepath:
                        downloaded.append(filepath)
                        if progress_callback:
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            progress_callback(f"✓ Downloaded: {os.path.basename(filepath)} ({size_mb:.2f} MB)")
                    elif status == "skipped" and progress_callback:
                        progress_callback(f"⊘ Skipped (already downloaded): {media_url[:60]}")
                    elif progress_callback:
                        # Show more detailed error message
                        error_detail = status if status else "unknown error"
                        progress_callback(f"✗ Failed: {media_url[:80]} - {error_detail}")
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"✗ Error downloading {media_url[:60]}: {str(e)[:50]}")
                
                processed += 1
                if progress_hook:
                    progress_hook(processed, bool(filepath) if 'filepath' in locals() else False)
        
        if downloaded:
            self.history.save_history()
        
        if progress_callback:
            success_rate = (len(downloaded) / len(all_items) * 100) if all_items else 0
            progress_callback(f"📊 Download complete: {len(downloaded)}/{len(all_items)} files ({success_rate:.1f}% success rate)")
        
        return downloaded

    def _download_with_fallback(self, media_url, download_path, source_url=None, progress_callback=None, force_yt_dlp=False):
        """Attempt to download media directly, then fallback to yt-dlp or gallery-dl if needed

        force_yt_dlp: when True, attempt yt-dlp even if the URL doesn't have a known video extension.
        """
        # For thothub.to video pages (not direct media), force yt-dlp to try extraction
        if 'thothub.to/videos/' in media_url and not any(ext in media_url.lower() for ext in ['.mp4', '.webm', '.m3u8', '.mov', '.avi', '.mkv', '.jpg', '.png', '.gif']):
            if progress_callback:
                progress_callback(f"🎬 thothub.to video page detected - trying yt-dlp extraction: {media_url[:80]}")
            force_yt_dlp = True
        
        if progress_callback:
            progress_callback(f"→ Attempting download: {media_url[:80]}...")
        
        # Check if this is a video URL
        is_video = any(ext in media_url.lower() for ext in ['.mp4', '.webm', '.m3u8', '.mov', '.avi', '.mkv'])

        # Quick filename-existence check: if a file with the same expected filename (or dl id)
        # already exists in download_path, skip download and return that path.
        try:
            parsed = urlparse(media_url)
            candidate_name = os.path.basename(parsed.path)
            # If path has an extension, use it directly
            if candidate_name and '.' in candidate_name:
                candidate_file = os.path.join(download_path, sanitize_filename(candidate_name))
                if os.path.exists(candidate_file):
                    if progress_callback:
                        progress_callback(f"Skipping download, file already exists: {candidate_file}")
                    return candidate_file
            # Check for query dl id (e.g., file.php?dl=ID)
            try:
                from urllib.parse import parse_qs
                qs = parse_qs(parsed.query)
                if 'dl' in qs and qs['dl']:
                    dlid = qs['dl'][0]
                    # Look for any file in download_path containing the id
                    for f in os.listdir(download_path):
                        if dlid in f:
                            found = os.path.join(download_path, f)
                            if progress_callback:
                                progress_callback(f"Skipping download, found existing file for dl id: {found}")
                            return found
            except Exception:
                pass
            # Otherwise, try matching by stem (same name without extension)
            stem = os.path.splitext(candidate_name)[0] if candidate_name else ''
            if stem:
                for f in os.listdir(download_path):
                    if f.startswith(stem):
                        found = os.path.join(download_path, f)
                        if progress_callback:
                            progress_callback(f"Skipping download, found existing file by stem: {found}")
                        return found
        except Exception:
            pass
        
        import tempfile
        import shutil

        # create temp dir for downloads to compute sha before finalizing
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix='scraper_tmp_')
        except Exception:
            temp_dir = None

        # For video URLs, or when explicitly forced, try yt-dlp first (better video handling)
        if is_video or force_yt_dlp:
            try:
                import subprocess
                # Generate filename from URL
                parsed_url = urlparse(media_url)
                base_filename = os.path.basename(parsed_url.path) or f"video_{hash(media_url)}"
                base_filename = sanitize_filename(os.path.splitext(base_filename)[0])
                # write to temp_dir if available so we can compute hash before finalizing
                out_dir_for_yt = temp_dir if temp_dir else download_path
                output_template = os.path.join(out_dir_for_yt, f"{base_filename}.%(ext)s")
                
                # Try yt-dlp for video downloads. Add referer/header if we have a source URL to help bypass simple wrappers.
                cmd = ['yt-dlp', '-o', output_template, '--no-warnings', '--no-playlist']
                
                # More aggressive options for difficult sites like thothub.to
                if 'thothub.to' in media_url:
                    cmd.extend([
                        '--retries', '10',
                        '--fragment-retries', '10',
                        '--extractor-retries', '5',
                        '--ignore-errors',
                    ])
                
                # If caller provided a source URL (the post page), pass it as Referer to yt-dlp
                try:
                    if source_url:
                        cmd.extend(['--add-header', f'Referer: {source_url}'])
                    ua = self.session.headers.get('User-Agent')
                    if ua:
                        cmd.extend(['--add-header', f'User-Agent: {ua}'])
                except Exception:
                    pass
                # Add the target URL last
                cmd.append(media_url)

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    # Find the downloaded file (in temp_dir or download_path)
                    search_dir = out_dir_for_yt
                    found_fp = None
                    for file in os.listdir(search_dir):
                        if file.startswith(base_filename):
                            found_fp = os.path.join(search_dir, file)
                            if progress_callback:
                                progress_callback(f"✓ Video downloaded via yt-dlp (temp): {file}")
                            break
                    if found_fp:
                        # compute sha and decide whether to keep or reuse existing
                        try:
                            sha = self._compute_sha256(found_fp)
                            if sha and self.history.is_sha_downloaded(sha):
                                # existing content present; return existing filepath if known
                                site, entry = self.history.get_entry_by_sha(sha)
                                existing_path = entry.get('filepath') if entry and isinstance(entry, dict) else None
                                # cleanup temp file
                                try:
                                    os.remove(found_fp)
                                except Exception:
                                    pass
                                if progress_callback:
                                    progress_callback(f"Duplicate detected by SHA — skipping save (sha={sha[:8]})")
                                if existing_path and os.path.exists(existing_path):
                                    return existing_path
                                return None
                            # move to final download_path
                            final_name = os.path.basename(found_fp)
                            final_path = os.path.join(download_path, final_name)
                            try:
                                shutil.move(found_fp, final_path)
                            except Exception:
                                final_path = found_fp
                            if progress_callback:
                                progress_callback(f"Saved video via yt-dlp: {os.path.basename(final_path)}")
                            return final_path
                        except Exception:
                            return found_fp
            except FileNotFoundError:
                # yt-dlp not installed, continue to standard download
                if progress_callback:
                    progress_callback(f"yt-dlp not found, trying direct download...")
            except subprocess.TimeoutExpired:
                if progress_callback:
                    progress_callback(f"yt-dlp timed out after 120s, trying direct download...")
            except Exception as e:
                if progress_callback:
                    error_output = result.stderr if 'result' in locals() and result.stderr else str(e)
                    progress_callback(f"yt-dlp failed: {error_output[:150]}")
                    if 'thothub.to' in media_url:
                        progress_callback(f"  → Video may be deleted, private, or require login")
        
        # Try standard download (stream to temp then compute sha)
        try:
            # Download into temp_dir if available to compute sha before finalizing
            download_target_dir = temp_dir if temp_dir else download_path
            filepath = self._download_media(media_url, download_target_dir, progress_callback=progress_callback)
            if filepath:
                # If we saved into temp_dir, compute sha and move or skip
                saved_in_temp = temp_dir and os.path.commonpath([os.path.abspath(filepath), os.path.abspath(temp_dir)]) == os.path.abspath(temp_dir)
                if saved_in_temp:
                    sha = self._compute_sha256(filepath)
                    if sha and self.history.is_sha_downloaded(sha):
                        # Duplicate found; remove temp and return existing
                        site, entry = self.history.get_entry_by_sha(sha)
                        existing_path = entry.get('filepath') if entry and isinstance(entry, dict) else None
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
                        if progress_callback:
                            progress_callback(f"Duplicate detected by SHA after download — skipping save (sha={sha[:8]})")
                        if existing_path and os.path.exists(existing_path):
                            return existing_path
                        return None
                    # move to final path
                    final_path = os.path.join(download_path, os.path.basename(filepath))
                    try:
                        import shutil
                        shutil.move(filepath, final_path)
                        filepath = final_path
                    except Exception:
                        pass
                return filepath
        except Exception:
            pass
        
        # Fallback to gallery-dl if available
        if self.gallery_dl and self.gallery_dl.gallery_dl_available:
            targets = []
            if media_url:
                targets.append(media_url)
            if source_url and source_url not in targets:
                targets.append(source_url)
            
            for target in targets:
                try:
                    files = self.gallery_dl.download_url(target, download_path, progress_callback)
                    if files:
                        return files[0]
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"gallery-dl fallback failed for {target}: {str(e)}")
        
        return None
    
    def _download_media(self, url, download_path, progress_callback=None):
        """Download media file from URL into the specified download_path (may be temp dir)."""
        try:
            # Add additional headers for better compatibility with some sites
            headers = {}
            
            # Special handling for thothub.to CDN - requires proper referer and headers
            if 'thothub.to' in url:
                # Use the main site as referer, not just the domain
                headers['Referer'] = 'https://thothub.to/'
                headers['Origin'] = 'https://thothub.to'
                headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                headers['Accept-Language'] = 'en-US,en;q=0.9'
                headers['Sec-Fetch-Dest'] = 'image'
                headers['Sec-Fetch-Mode'] = 'no-cors'
                headers['Sec-Fetch-Site'] = 'same-origin'
            
            response = self.session.get(url, timeout=30, stream=True, headers=headers if headers else None)
            
            # Check for errors and provide better feedback
            if response.status_code == 403:
                if progress_callback:
                    progress_callback(f"❌ HTTP 403 Forbidden: {url[:80]} - Site blocking access")
                return None
            elif response.status_code == 404:
                if progress_callback:
                    progress_callback(f"❌ HTTP 404 Not Found: {url[:80]} - File doesn't exist")
                return None
            elif response.status_code >= 400:
                if progress_callback:
                    progress_callback(f"❌ HTTP {response.status_code}: {url[:80]}")
                return None
            
            response.raise_for_status()

            # Get filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            # Special handling for thothub.to URLs - they often have IDs in the path
            if 'thothub.to' in url and '/contents/' in url:
                # Extract meaningful filename from path
                path_parts = parsed_url.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    # Use last two parts as filename (e.g., "videos_screenshots_12345_67890")
                    filename = '_'.join(path_parts[-2:])
            
            if not filename:
                filename = 'media_file'

            filename = sanitize_filename(filename)

            # Ensure we have an extension
            if not any(filename.lower().endswith(ext) for ext in 
                      ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.mov']):
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    if 'jpeg' in content_type:
                        filename += '.jpg'
                    elif 'png' in content_type:
                        filename += '.png'
                    elif 'gif' in content_type:
                        filename += '.gif'
                    else:
                        filename += '.jpg'
                elif 'video' in content_type:
                    filename += '.mp4'
                else:
                    if progress_callback:
                        progress_callback(f"Skipping unknown content-type: {content_type}")
                    return None  # Skip unknown file types

            filepath = os.path.join(download_path, filename)

            # Skip if file already exists
            if os.path.exists(filepath):
                return None
            
            # Check if URL already downloaded (duplicate check)
            if self.duplicate_checker and self.duplicate_checker.is_duplicate_url(url, verify_exists=True):
                if progress_callback:
                    progress_callback(f"Skipping duplicate URL: {url[:80]}")
                return None

            # Download file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Add to duplicate tracker after successful download
            if self.duplicate_checker:
                self.duplicate_checker.add_file(filepath, source_url=url)

            return filepath

        except requests.exceptions.HTTPError as e:
            # Log HTTP errors (404, 403, etc.)
            if progress_callback:
                progress_callback(f"HTTP error {e.response.status_code}: {url[:80]}")
            return None
        except requests.exceptions.Timeout:
            if progress_callback:
                progress_callback(f"Timeout downloading: {url[:80]}")
            return None
        except requests.exceptions.ConnectionError:
            if progress_callback:
                progress_callback(f"Connection error: {url[:80]}")
            return None
        except Exception as e:
            # Log other errors for debugging
            if progress_callback:
                progress_callback(f"Download error ({type(e).__name__}): {str(e)[:100]}")
            return None
