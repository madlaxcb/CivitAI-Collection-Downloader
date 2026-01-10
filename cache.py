import os
import json
import shutil
import hashlib
import logging
import requests
import time
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw
import io

from config import config

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages application cache for data and images."""
    
    def __init__(self):
        self._ensure_directories()
        
    def _ensure_directories(self):
        """Ensure cache directories exist."""
        self.cache_root = Path(config.get('cache_dir', os.path.join(os.path.expanduser('~'), '.civitai_downloader', 'cache')))
        self.data_cache_dir = self.cache_root / 'data'
        self.image_cache_dir = self.cache_root / 'images'
        
        try:
            self.data_cache_dir.mkdir(parents=True, exist_ok=True)
            self.image_cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create cache directories: {e}")

    def get_cache_size(self):
        """Get current cache size in MB."""
        total_size = 0
        try:
            for dir_path in [self.data_cache_dir, self.image_cache_dir]:
                if dir_path.exists():
                    for path in dir_path.rglob('*'):
                        if path.is_file():
                            total_size += path.stat().st_size
            return total_size / (1024 * 1024)
        except Exception as e:
            logger.error(f"Error calculating cache size: {e}")
            return 0

    def clear_cache(self):
        """Clear all cache files."""
        try:
            if self.cache_root.exists():
                shutil.rmtree(self.cache_root)
            self._ensure_directories()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def _check_size_limit(self):
        """Check if cache size exceeds limit and cleanup if necessary."""
        max_size = config.get('max_cache_size', 500) # MB
        current_size = self.get_cache_size()
        
        if current_size > max_size:
            logger.info(f"Cache size ({current_size:.2f} MB) exceeds limit ({max_size} MB). Cleaning up...")
            self._cleanup_old_files()

    def _cleanup_old_files(self):
        """Delete oldest files until size is within limit."""
        # This is a simple implementation: delete files sorted by access time
        all_files = []
        for dir_path in [self.data_cache_dir, self.image_cache_dir]:
            if dir_path.exists():
                for path in dir_path.rglob('*'):
                    if path.is_file():
                        all_files.append((path, path.stat().st_atime))
        
        # Sort by access time (oldest first)
        all_files.sort(key=lambda x: x[1])
        
        max_size_bytes = config.get('max_cache_size', 500) * 1024 * 1024
        current_size_bytes = sum(f[0].stat().st_size for f in all_files)
        
        for file_path, _ in all_files:
            if current_size_bytes <= max_size_bytes:
                break
            
            try:
                size = file_path.stat().st_size
                file_path.unlink()
                current_size_bytes -= size
            except Exception as e:
                logger.warning(f"Failed to delete cache file {file_path}: {e}")

    # Data Cache Methods
    def save_data(self, key, data):
        """Save data to cache."""
        try:
            file_path = self.data_cache_dir / f"{key}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving data cache {key}: {e}")

    def load_data(self, key):
        """Load data from cache."""
        try:
            file_path = self.data_cache_dir / f"{key}.json"
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data cache {key}: {e}")
        return None

    # Image Cache Methods
    def get_cached_image(self, url):
        """Get image path from cache if exists."""
        if not url:
            return None
            
        file_name = hashlib.md5(url.encode()).hexdigest()
        file_path = self.image_cache_dir / file_name
        
        if file_path.exists():
            # Update access time
            try:
                file_path.touch()
            except:
                pass
            return file_path
        return None

    def save_image(self, url, content):
        """Save image content to cache."""
        if not url or not content:
            return None
            
        try:
            self._check_size_limit()
            
            file_name = hashlib.md5(url.encode()).hexdigest()
            file_path = self.image_cache_dir / file_name
            
            with open(file_path, 'wb') as f:
                f.write(content)
                
            return file_path
        except Exception as e:
            logger.error(f"Error saving image cache: {e}")
            return None

    def get_cached_video_path(self, url):
        """Get video path from cache, downloading if necessary."""
        if not url:
            return None
            
        # Fix CivitAI video URL if missing /original=true
        if "image.civitai.com" in url and "original=true" not in url and "width=" not in url:
             if '?' in url:
                 url += "&original=true"
             else:
                 url = url.rstrip('/') + "/original=true"
             logger.debug(f"Fixed video URL in cache manager: {url}")
            
        cached_path = self.get_cached_image(url) # Reusing get_cached_image as it just checks existence by hash
        
        if cached_path:
            return str(cached_path)
            
        try:
            proxies = config.get_proxies()
            response = requests.get(url, proxies=proxies, stream=True, timeout=30)
            response.raise_for_status()
            
            # Save to cache (streaming)
            self._check_size_limit()
            file_name = hashlib.md5(url.encode()).hexdigest()
            file_path = self.image_cache_dir / file_name
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error caching video {url}: {e}")
            return None

    def _create_placeholder(self, text, max_size):
        """Create a placeholder image with text."""
        w, h = max_size
        img = Image.new('RGB', max_size, color=(220, 220, 220))
        draw = ImageDraw.Draw(img)
        
        # Draw text roughly centered
        try:
            # Draw a box border
            draw.rectangle([(0,0), (w-1, h-1)], outline=(100,100,100), width=2)
            # Draw text
            text_color = (0, 0, 0)
            draw.text((w//2 - 20, h//2 - 10), text, fill=text_color)
        except Exception:
            pass
            
        return img

    def get_preview_file(self, url):
        """
        Get preview file path and type.
        Downloads if necessary.
        Returns: (path, type) where type is 'image', 'video', or 'unknown'
        """
        # Ensure we have the preview URL format if it's a CivitAI video URL
        # But caller usually handles this. If not, we could check here.
        
        path = self.get_cached_image(url)
        
        if not path:
            try:
                proxies = config.get_proxies()
                # Use headers to request image if possible, but accept anything
                headers = {
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                }
                response = requests.get(url, proxies=proxies, timeout=30, headers=headers)
                response.raise_for_status()
                path = self.save_image(url, response.content)
                if not path:
                    return None, None
            except Exception as e:
                logger.error(f"Error downloading preview {url}: {e}")
                return None, None
                
        # Determine type
        try:
            # Check for video signature (ftyp)
            with open(path, 'rb') as f:
                header = f.read(12)
                if b'ftyp' in header:
                    return str(path), 'video'
            
            # Check for image (try opening with PIL)
            try:
                Image.open(path).verify()
                return str(path), 'image'
            except:
                pass
                
            # If we are here, it might be something else or corrupt
            return str(path), 'unknown'
            
        except Exception as e:
            logger.error(f"Error checking preview file type: {e}")
            return str(path), 'unknown'

    def get_image_preview(self, url, max_size=(300, 300)):
        """Get ImageTk for preview, using cache if available."""
        cached_path = self.get_cached_image(url)
        img = None
        
        try:
            if cached_path:
                try:
                    img = Image.open(cached_path)
                    img.load() # Verify it loads
                except Exception:
                    # If cache file is invalid/corrupt or not an image
                    logger.warning(f"Invalid cache file for {url}, removing...")
                    try:
                        os.remove(cached_path)
                    except:
                        pass
                    cached_path = None # Trigger download logic
            
            if not cached_path:
                # Download
                proxies = config.get_proxies()
                response = requests.get(url, proxies=proxies, timeout=10)
                response.raise_for_status()
                
                content_type = response.headers.get('Content-Type', '').lower()
                if 'video' in content_type:
                    # It's a video, return placeholder
                    img = self._create_placeholder("VIDEO", max_size)
                    return ImageTk.PhotoImage(img)

                content = response.content
                
                # Try to open to verify it's an image before saving
                try:
                    Image.open(io.BytesIO(content)).verify()
                    # Re-open for usage
                    img = Image.open(io.BytesIO(content))
                    # Save to cache
                    self.save_image(url, content)
                except Exception as e:
                    logger.warning(f"Downloaded content is not a valid image: {e}")
                    img = self._create_placeholder("INVALID", max_size)
                    return ImageTk.PhotoImage(img)
            
            img.thumbnail(max_size)
            return ImageTk.PhotoImage(img)
            
        except Exception as e:
            logger.error(f"Error loading preview for {url}: {e}")
            img = self._create_placeholder("ERROR", max_size)
            return ImageTk.PhotoImage(img)

cache_manager = CacheManager()
