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
from config import get_image_cdn_base, get_image_cdn_domain

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
    if not filename:
        return "unnamed"
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
            url = f"{get_image_cdn_base()}/{cdn_key}/{url}/width={width}"
        else:
            url = f"{get_image_cdn_base()}/{cdn_key}/{url}/original=true"
        logger.debug(f"Constructed download URL from '{original_url}' to '{url}'")

    # Add original=true for videos if missing (even for http URLs)
    # But only if we haven't already specified a width or other modifier
    if mime_type and mime_type.startswith('video'):
        if 'width=' in url or 'transcode=' in url or 'format=' in url:
            pass
        elif get_image_cdn_domain() in url and 'original=true' not in url:
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
    media_name = media_data.get("name") or f"media-{media_id}"
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

def create_model_directory(model_name, model_id=None):
    """Create a directory named after the model under download_dir."""
    download_dir = config.get('download_dir')
    if not download_dir:
        download_dir = os.path.join(os.path.expanduser('~'), 'Pictures', 'CivitAI')
        logger.warning(f"Download directory not found in config, using default: {download_dir}")

    safe_name = sanitize_filename(model_name or f"Model-{model_id or 'unknown'}")
    if model_id is not None:
        dir_name = f"{model_id}-{safe_name}"
    else:
        dir_name = safe_name

    model_dir = Path(download_dir) / dir_name
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir

def get_free_disk_space(path):
    """Return free disk space in bytes for the filesystem containing ``path``."""
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        path = path if path.exists() else path.parent
    return shutil.disk_usage(str(path)).free


def check_disk_space(path, required_bytes, margin_ratio=0.05, min_margin_bytes=50 * 1024 * 1024):
    """Return (ok, free_bytes, needed_bytes). Adds 5% / 50MB safety margin."""
    free = get_free_disk_space(path)
    if required_bytes is None or required_bytes <= 0:
        return True, free, 0
    margin = max(int(required_bytes * margin_ratio), int(min_margin_bytes))
    needed = int(required_bytes) + margin
    return free >= needed, free, needed


def _parse_content_range_total(content_range):
    """Parse total size from Content-Range header, e.g. 'bytes 100-999/1234'."""
    if not content_range:
        return None
    try:
        total_part = content_range.split('/')[-1].strip()
        if total_part == '*':
            return None
        return int(total_part)
    except (ValueError, IndexError):
        return None


def download_model_file(url, dest_path, api_key=None, progress_callback=None, expected_size=None):
    """Download a large model file with HTTP Range resume support and disk space checks.

    Args:
        url: Download URL (usually /api/download/models/{versionId} or file downloadUrl)
        dest_path: Target file Path
        api_key: Optional API key for Authorization header
        progress_callback: Optional callable(downloaded_bytes, total_bytes)
        expected_size: Optional known file size in bytes (e.g. from sizeKB * 1024)
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + '.part')

    # Already complete?
    if dest_path.exists() and dest_path.stat().st_size > 0:
        if expected_size and dest_path.stat().st_size < expected_size * 0.99:
            logger.warning(
                f"Existing file size mismatch ({dest_path.stat().st_size} < {expected_size}), re-downloading"
            )
            dest_path.unlink()
        else:
            logger.info(f"Model file already exists: {dest_path}")
            return dest_path

    # Disk space check (account for already-downloaded .part bytes)
    existing_part = temp_path.stat().st_size if temp_path.exists() else 0
    if expected_size and expected_size > 0:
        remaining = max(0, int(expected_size) - existing_part)
        ok, free, needed = check_disk_space(dest_path.parent, remaining)
        if not ok:
            logger.error(
                f"Insufficient disk space for {dest_path.name}: "
                f"need ~{needed/1024/1024:.1f} MB free, have {free/1024/1024:.1f} MB"
            )
            return None

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Encoding': 'identity',
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    max_retries = config.get('max_retries', 3)
    for attempt in range(max_retries):
        try:
            resume_pos = temp_path.stat().st_size if temp_path.exists() else 0
            req_headers = dict(headers)
            if resume_pos > 0:
                req_headers['Range'] = f'bytes={resume_pos}-'
                logger.info(f"Resuming model download from byte {resume_pos}: {dest_path.name}")

            with requests.get(
                url,
                headers=req_headers,
                proxies=config.get_proxies(),
                stream=True,
                timeout=60,
                allow_redirects=True
            ) as response:
                # 416 = invalid range → restart
                if response.status_code == 416:
                    logger.warning(f"Server returned 416 for {dest_path.name}, restarting download")
                    if temp_path.exists():
                        temp_path.unlink()
                    resume_pos = 0
                    continue

                # If server ignores Range and returns 200, restart from scratch
                if response.status_code == 200 and resume_pos > 0:
                    logger.warning(f"Server does not support resume, restarting: {dest_path.name}")
                    resume_pos = 0
                    if temp_path.exists():
                        temp_path.unlink()

                if response.status_code not in (200, 206):
                    response.raise_for_status()

                # Resolve total size: Content-Range > Content-Length + offset > expected_size
                total = _parse_content_range_total(response.headers.get('Content-Range'))
                if total is None:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        total = int(content_length) + resume_pos
                if total is None and expected_size:
                    total = int(expected_size)

                # Re-check space once we know the real total
                if total:
                    remaining = max(0, total - resume_pos)
                    ok, free, needed = check_disk_space(dest_path.parent, remaining)
                    if not ok:
                        logger.error(
                            f"Insufficient disk space for {dest_path.name}: "
                            f"need ~{needed/1024/1024:.1f} MB free, have {free/1024/1024:.1f} MB"
                        )
                        return None

                mode = 'ab' if resume_pos > 0 and response.status_code == 206 else 'wb'
                if mode == 'wb' and resume_pos > 0:
                    resume_pos = 0
                downloaded = resume_pos

                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)

            # Validate size when known
            final_size = temp_path.stat().st_size if temp_path.exists() else 0
            if total and final_size < total:
                raise IOError(f"Incomplete download: got {final_size} bytes, expected {total}")
            if expected_size and final_size < expected_size * 0.99 and not total:
                logger.warning(
                    f"Downloaded size {final_size} is much smaller than expected {expected_size}"
                )

            # Move completed part file into place
            if dest_path.exists():
                dest_path.unlink()
            temp_path.replace(dest_path)
            logger.info(f"Downloaded model file: {dest_path} ({final_size} bytes)")
            return dest_path
        except Exception as e:
            logger.error(f"Model download attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                logger.info(f"Partial file retained for resume: {temp_path}")
                return None
            time.sleep(2 ** attempt)

    return None

def download_model_image(url, dest_path, api_key=None):
    """Download a model example/preview image."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        with requests.get(url, headers=headers, proxies=config.get_proxies(), stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        logger.info(f"Downloaded model image: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Failed to download model image {url}: {e}")
        return None