import os
import sys
import json
import time
import logging
import requests
import mimetypes
import shutil
from pathlib import Path
from urllib.parse import urlparse

from config import config
from cache import cache_manager
from api import get_cdn_key

logger = logging.getLogger(__name__)

# Initialize mimetypes
mimetypes.init()
# Ensure common MIME types are properly mapped
mimetypes.add_type('image/jpeg', '.jpg')
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('video/mp4', '.mp4')

def get_file_extension(mime_type):
    """Get the appropriate file extension for a MIME type."""
    # Special case handling for common types
    mime_to_ext = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'video/mp4': '.mp4',
        'video/quicktime': '.mov',
        'video/webm': '.webm'
    }

    if mime_type in mime_to_ext:
        return mime_to_ext[mime_type]

    # Fall back to system MIME type mapping
    ext = mimetypes.guess_extension(mime_type)
    return ext or ''

def sanitize_filename(filename):
    """Sanitize filename to be filesystem-safe."""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')

    # Replace spaces with underscores for consistency
    filename = filename.replace(' ', '_')

    # Limit length to avoid filesystem issues
    if len(filename) > 200:
        base, ext = os.path.splitext(filename)
        filename = base[:200] + ext

    return filename

def create_download_directory(collection_info):
    """Create a directory for downloading files based on collection info."""
    # Ensure we have a valid download directory
    download_dir = config.get('download_dir')
    if not download_dir:
        download_dir = os.path.join(os.path.expanduser('~'), 'Pictures', 'CivitAI')
        logger.warning(f"Download directory not found in config, using default: {download_dir}")

    base_dir = Path(download_dir)

    # Handle different types of input for collection_info
    if collection_info is None:
        # Use ID from command line args as fallback
        collection_id = "unknown-collection"
        if len(sys.argv) > 2 and sys.argv[1] in ['-c', '--collection']:
            collection_id = sys.argv[2]
        logger.warning(f"No collection info available, using ID: {collection_id}")
        download_dir = base_dir / str(collection_id)
    elif isinstance(collection_info, dict) and "collection" in collection_info:
        # Full collection object from API
        collection_name = collection_info.get("collection", {}).get("name")
        collection_id = collection_info.get("collection", {}).get("id")

        # Create directory name based on collection ID and name
        if collection_name:
            dir_name = f"{collection_id}-{sanitize_filename(collection_name)}"
        else:
            dir_name = f"{collection_id}"

        download_dir = base_dir / dir_name
    else:
        # Assume collection_info is just the ID
        collection_id = collection_info
        download_dir = base_dir / str(collection_id)

    # Create the directory
    download_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Created download directory: {download_dir}")
    return download_dir

def download_file(url, output_path, mime_type=None, max_retries=3, api_key=None, width=None):
    """Download a file from a URL to the specified path with retry logic and caching."""
    # Ensure URL is complete with domain if it's just a path
    if not url.startswith('http'):
        # CivitAI Image CDN Key (automatic)
        cdn_key = get_cdn_key()
        
        # Extract filename from the output path
        filename = os.path.basename(output_path)

        # Construct URL using the CDN key
        original_url = url
        
        # Use width for videos if available, otherwise fallback to original=true
        if mime_type and mime_type.startswith('video') and width:
            url = f"https://image.civitai.com/{cdn_key}/{url}/width={width}"
        else:
            # Use original=true to ensure we get the highest quality file
            url = f"https://image.civitai.com/{cdn_key}/{url}/original=true"
        logger.debug(f"Constructed download URL from '{original_url}' to '{url}'")

    # Add original=true for videos if missing (even for http URLs)
    # But only if we haven't already specified a width or other modifier
    if mime_type and mime_type.startswith('video'):
        if 'width=' in url or 'transcode=' in url or 'format=' in url:
            pass
        elif 'image.civitai.com' in url and 'original=true' not in url:
             # For CivitAI, it's a path component
             url = url.rstrip('/') + "/original=true"
        elif 'original=true' not in url and '?' in url:
            url += "&original=true"
        elif 'original=true' not in url:
            url += "?original=true"
        
        if 'original=true' in url:
            logger.debug(f"Added original=true to video URL: {url}")

    # Check cache first
    cached_file = cache_manager.get_cached_image(url)
    if cached_file:
        logger.info(f"File found in cache: {cached_file}")
        try:
            shutil.copy2(cached_file, output_path)
            logger.info(f"Restored from cache to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy from cache: {e}")
            # Fallback to download if copy fails
    
    logger.info(f"Downloading file to {output_path}")
    logger.debug(f"Download URL: {url}")

    for attempt in range(max_retries + 1):
        try:
            # Simple request without session, exactly like original script
            logger.debug(f"Download attempt {attempt+1}/{max_retries+1}")
            
            # Download to a temporary file first (or directly to cache if we want to stream to cache)
            # To be safe and efficient, let's download to output_path first, then copy to cache.
            # This avoids double writing if cache is not needed or fails.
            # BUT, the requirement is "download cache". So we should put it in cache.
            
            # Let's stream to cache file first.
            import hashlib
            cache_key = hashlib.md5(url.encode()).hexdigest()
            cache_path = cache_manager.image_cache_dir / cache_key
            
            # Ensure cache dir exists (it should)
            cache_manager._ensure_directories()
            
            with requests.get(url, stream=True, proxies=config.get_proxies()) as response:
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                response.raise_for_status()

                # Check if MIME type matches expected
                content_type = response.headers.get('Content-Type', '')
                if mime_type and content_type and not content_type.startswith(mime_type):
                    logger.warning(f"MIME type mismatch. Expected: {mime_type}, Got: {content_type}")

                # Save the file to cache
                logger.debug(f"Writing file to cache: {cache_path}")
                with open(cache_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            # Now copy to output_path
            shutil.copy2(cache_path, output_path)
            
            # Trigger cache cleanup check
            cache_manager._check_size_limit()

            logger.debug(f"Successfully downloaded file to {output_path}")
            return True

        except (requests.RequestException, OSError) as e:
            logger.error(f"Error downloading file (attempt {attempt+1}/{max_retries+1}): {e}")
            if 'response' in locals():
                logger.debug(f"Response headers: {dict(response.headers) if hasattr(response, 'headers') else 'No headers'}")
                logger.debug(f"Response content: {response.text[:200] if hasattr(response, 'text') else 'No content'}")

            if attempt < max_retries:
                delay = attempt + 1  # Incremental backoff
                logger.info(f"Retrying download in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"Download failed after {max_retries+1} attempts")
                return False

def download_media(media_data, download_dir, api_key=None):
    """Download an image or video and return its file path."""
    media_id = media_data.get("id")
    media_name = media_data.get("name", f"media-{media_id}")
    media_url = media_data.get("url")
    mime_type = media_data.get("mimeType", "image/jpeg")

    if not media_url:
        logger.error(f"No URL found for media {media_id}")
        return None

    # Sanitize filename and add proper extension
    base_name = sanitize_filename(media_name)
    base_name, _ = os.path.splitext(base_name)  # Remove any existing extension
    extension = get_file_extension(mime_type)
    file_name = f"{base_name}{extension}"

    # Full path for the file
    file_path = Path(download_dir) / file_name

    # Skip if file already exists
    if file_path.exists():
        logger.info(f"File already exists: {file_path}")
        return file_path

    # Try to get width from various locations in the data
    width = media_data.get('width')
    if not width and 'metadata' in media_data:
        width = media_data.get('metadata', {}).get('width')
    if not width:
         width = media_data.get('originalWidth')

    # Download the file
    success = download_file(
        media_url,
        file_path,
        mime_type=mime_type,
        max_retries=config.get('max_retries', 3),
        api_key=api_key,
        width=width
    )

    if success:
        return file_path  # Return Path object
    else:
        return None

def save_metadata(metadata, file_path):
    """Save metadata to a JSON file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved metadata to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving metadata to {file_path}: {e}")
        return False