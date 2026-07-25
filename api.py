import time
import json
import logging
import requests
import re
from urllib.parse import quote

from config import config, get_site_base_url, get_image_cdn_base, get_image_cdn_domain

logger = logging.getLogger(__name__)

_CACHED_CDN_KEY = None

def get_cdn_key():
    """Automatically retrieve the CDN key from CivitAI homepage."""
    global _CACHED_CDN_KEY
    if _CACHED_CDN_KEY:
        return _CACHED_CDN_KEY
    
    # Check config first
    config_key = config.get('cdn_key')
    if config_key and config_key.strip():
        logger.info(f"Using CDN Key from config: {config_key}")
        _CACHED_CDN_KEY = config_key.strip()
        return _CACHED_CDN_KEY
        
    logger.info("Attempting to retrieve CDN Key via API...")
    cdn_domain = get_image_cdn_domain()

    try:
        # Use the REST API to get a model with images (model ID 1 is lightweight, ~4KB)
        api_url = get_site_base_url() + "/api/v1/models/1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        api_key = config.get('api_key')
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        response = requests.get(api_url, headers=headers, timeout=10, proxies=config.get_proxies())
        response.raise_for_status()
        data = response.json()

        # Extract CDN key from the first image URL in the model's version images
        for version in (data.get('modelVersions') or []):
            for img in (version.get('images') or []):
                img_url = img.get('url', '')
                matches = re.findall(rf'https://{re.escape(cdn_domain)}/([^/]+)/', img_url)
                if matches:
                    key = matches[0]
                    logger.info(f"Successfully retrieved CDN Key via API: {key}")
                    _CACHED_CDN_KEY = key
                    return key

        logger.info("Could not find CDN Key in API response. Using fallback.")
    except Exception as e:
        logger.warning(f"Error retrieving CDN Key via API: {e}")
        
    # Fallback key (the one we know works currently)
    fallback = 'xG1nkqKTMzGDvpLrqFT7WA'
    logger.info(f"Using fallback CDN Key: {fallback}")
    _CACHED_CDN_KEY = fallback
    return fallback

class CivitaiAPI:
    """Client for interacting with CivitAI's TRPC API."""
    
    BASE_URL = "https://civitai.com/api/trpc"
    
    def __init__(self, api_key=None):
        """Initialize the API client with the provided API key."""
        self.api_key = api_key or config.get('api_key')
        self._update_base_url()
        
    def _update_base_url(self):
        self.BASE_URL = get_site_base_url() + "/api/trpc"
        
        # Check if API key is available
        if not self.api_key:
            logger.warning("No API key found! Please make sure you have set your API key in the configuration.")
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        else:
            # Simple authorization header, exactly like the original script
            self.headers = {
                'Authorization': 'Bearer ' + self.api_key,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

    @staticmethod
    def _decode_devalue(root):
        """Decode a superjson/devalue serialized array into native Python objects.

        The root array holds all unique values. Index 0 is the root schema.
        - ``-1`` means undefined (returns None)
        - Objects are schemas mapping keys to indices
        - Empty lists are literal empty arrays
        - Lists starting with a string are type markers (e.g. ``["Date", iso]``)
        - Other lists contain integer indices to resolve
        - Primitives are returned as-is
        """
        def resolve(index):
            if index == -1:
                return None
            value = root[index]
            if isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            if isinstance(value, list):
                if len(value) == 0:
                    return []
                # Special type marker: ["Date", "2026-07-21T..."]
                if isinstance(value[0], str):
                    return value[1] if len(value) >= 2 else None
                # Array of indices
                return [resolve(i) for i in value]
            return value
        return resolve(0)

    def _parse_trpc_data(self, result):
        """Parse TRPC response data, handling both standard and devalue formats.

        Most endpoints return ``result.data`` as a dict with a ``json`` key.
        The ``image.getInfinite`` endpoint returns ``result.data`` as a
        superjson devalue string instead.
        """
        data = result.get("result", {}).get("data", {})
        if isinstance(data, dict):
            return data.get("json")
        if isinstance(data, str):
            try:
                return self._decode_devalue(json.loads(data))
            except Exception as e:
                logger.error(f"Failed to decode TRPC devalue response: {e}")
                return None
        return data if data else None
    
    def create_collection(self, name, description="", read="Private", write="Private", type="Image", nsfw=False, collection_id=None):
        """Create or update a collection."""
        if collection_id:
            logger.info(f"Updating collection: {name} ({collection_id})")
        else:
            logger.info(f"Creating collection: {name}")
        
        # Using upsert as it's common for create/update in TRPC
        url = f"{self.BASE_URL}/collection.upsert"
        
        try:
            payload = {
                "json": {
                    "name": name,
                    "description": description,
                    "read": read,
                    "write": write,
                    "type": type,
                    "nsfw": nsfw
                }
            }
            
            if collection_id:
                payload["json"]["id"] = int(collection_id)
            
            response = requests.post(url, json=payload, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            
            result = response.json()
            action = "updated" if collection_id else "created"
            logger.info(f"Collection {action}: {result}")
            return result.get('result', {}).get('data', {}).get('json')
            
        except Exception as e:
            action = "updating" if collection_id else "creating"
            logger.error(f"Error {action} collection {name}: {e}")
            if 'response' in locals() and response is not None:
                 logger.error(f"Error details: {response.text}")
            return None

    def delete_collection(self, collection_id):
        """Delete a collection."""
        logger.info(f"Deleting collection: {collection_id}")
        
        url = f"{self.BASE_URL}/collection.delete"
        
        payload = {
            "json": {
                "id": int(collection_id)
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error deleting collection {collection_id}: {e}")
            if 'response' in locals() and response is not None:
                 logger.error(f"Error details: {response.text}")
            return False

    def get_collection_by_id(self, collection_id):
        """Get details of a collection by its ID."""
        logger.info(f"Fetching collection with ID: {collection_id}")
        
        # Create request data
        request_data = {
            "json": {
                "id": int(collection_id),
                "authed": True
            }
        }
        
        # Encode parameters
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/collection.getById?input={encoded_input}"
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            return result.get("result", {}).get("data", {}).get("json")
        except Exception as e:
            logger.error(f"Error fetching collection {collection_id}: {e}")
            return None
    
    def get_images_in_collection(self, collection_id, cursor=None):
        """Get images in a collection with pagination support."""
        # Create the request data exactly like the working script
        request_data = {
            "json": {
                "collectionId": int(collection_id),
                "period": "AllTime",
                "sort": "Newest",
                "browsingLevel": 31,  # 31 = 1(PG) + 2(PG-13) + 4(R) + 8(X) + 16(XXX)
                "include": ["cosmetics"],
                "cursor": cursor,
                "authed": True
            }
        }
        
        # Add meta field only for the first request (when cursor is None)
        if cursor is None:
            request_data["meta"] = {"values": {"cursor": ["undefined"]}}
        
        # Construct the URL exactly like the working script
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/image.getInfinite?input={encoded_input}"
        
        logger.info(f"Fetching images in collection {collection_id}{' with cursor' if cursor else ''}")
        logger.debug(f"Request URL: {url}")
        logger.debug(f"Request headers: {self.headers}")
        logger.debug(f"Request data: {request_data}")
        
        try:
            # Make direct request with authorization header and proxy
            proxies = config.get_proxies()
            logger.debug(f"Using proxies: {proxies}")
            response = requests.get(url, headers=self.headers, proxies=proxies)
            
            logger.debug(f"Response status code: {response.status_code}")
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"Response received: {result.keys()}")
            
            # Extract the data (handles both standard and devalue formats)
            parsed = self._parse_trpc_data(result)
            if not parsed or not isinstance(parsed, dict):
                logger.debug(f"No data returned for collection {collection_id}")
                return {"items": [], "nextCursor": None}
            items = parsed.get('items', [])
            next_cursor = parsed.get('nextCursor')
            
            logger.debug(f"Retrieved {len(items)} items, next cursor: {next_cursor}")
            
            return {
                "items": items,
                "nextCursor": next_cursor
            }
            
        except Exception as e:
            logger.error(f"Error fetching images from collection {collection_id}: {e}")
            if 'response' in locals():
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
            return {"items": [], "nextCursor": None}
    
    def get_all_images_in_collection(self, collection_id):
        """Get all images in a collection by handling pagination."""
        all_images = []
        cursor = None
        batch_count = 0
        
        logger.info(f"Starting retrieval of all images from collection {collection_id}")
        
        while True:
            batch_count += 1
            logger.debug(f"Retrieving batch #{batch_count} of images...")
            
            result = self.get_images_in_collection(collection_id, cursor)
            if not result or not result.get("items"):
                if not all_images:  # No images retrieved at all
                    logger.error(f"No images found in collection {collection_id}")
                break
                
            batch_items = result.get("items", [])
            logger.debug(f"Retrieved batch of {len(batch_items)} images from collection {collection_id}")
            
            # Log some details about the first few items
            if batch_items and len(batch_items) > 0 and batch_count == 1:
                first_item = batch_items[0]
                logger.debug(f"First item sample - ID: {first_item.get('id')}, Name: {first_item.get('name')}, URL: {first_item.get('url')}")
            
            all_images.extend(batch_items)
            
            cursor = result.get("nextCursor")
            logger.debug(f"Next cursor: {cursor}")
            
            if not cursor:
                logger.debug("No more pages to retrieve")
                break
        
        logger.info(f"Retrieved a total of {len(all_images)} images from collection {collection_id}")
        return all_images
    
    def get_post_by_id(self, post_id):
        """Get details of a post by its ID."""
        logger.info(f"Fetching post with ID: {post_id}")
        
        # Create request data
        request_data = {
            "json": {
                "id": int(post_id),
                "authed": True
            }
        }
        
        # Encode parameters
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/post.get?input={encoded_input}"
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            return result.get("result", {}).get("data", {}).get("json")
        except Exception as e:
            logger.error(f"Error fetching post {post_id}: {e}")
            return None
    
    def get_images_in_post(self, post_id, cursor=None):
        """Get images in a post with pagination support."""
        # Create the request data
        request_data = {
            "json": {
                "postId": int(post_id),
                "browsingLevel": 31,  # 31 = 1(PG) + 2(PG-13) + 4(R) + 8(X) + 16(XXX)
                "cursor": cursor,
                "authed": True
            }
        }
        
        # Add meta field only for the first request (when cursor is None)
        if cursor is None:
            request_data["meta"] = {"values": {"cursor": ["undefined"]}}
        
        # Construct the URL
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/image.getInfinite?input={encoded_input}"
        
        logger.info(f"Fetching images in post {post_id}{' with cursor' if cursor else ''}")
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            # Extract the data (handles both standard and devalue formats)
            parsed = self._parse_trpc_data(result)
            if not parsed or not isinstance(parsed, dict):
                parsed = {}
            items = parsed.get('items', [])
            next_cursor = parsed.get('nextCursor')
            
            logger.debug(f"Retrieved {len(items)} images from post {post_id}")
            
            return {
                "items": items,
                "nextCursor": next_cursor
            }
            
        except Exception as e:
            logger.error(f"Error fetching images from post {post_id}: {e}")
            return {"items": [], "nextCursor": None}
    
    def get_all_images_in_post(self, post_id):
        """Get all images in a post by handling pagination."""
        all_images = []
        cursor = None
        
        while True:
            result = self.get_images_in_post(post_id, cursor)
            if not result or not result.get("items"):
                break
                
            all_images.extend(result.get("items", []))
            cursor = result.get("nextCursor")
            
            if not cursor:
                break
                
            logger.debug(f"Retrieved {len(result['items'])} images, continuing with next page")
        
        logger.info(f"Retrieved a total of {len(all_images)} images from post {post_id}")
        return all_images

    def get_images_by_username(self, username, cursor=None):
        """Get images for a user with pagination support."""
        # Create the request data
        request_data = {
            "json": {
                "username": username,
                "period": "AllTime",
                "sort": "Newest",
                "browsingLevel": 31,
                "types": ["image", "video"],
                "include": ["cosmetics"],
                "cursor": cursor,
                "authed": True
            }
        }
        
        # Add meta field only for the first request (when cursor is None)
        if cursor is None:
            request_data["meta"] = {"values": {"cursor": ["undefined"]}}
        
        # Construct the URL
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/image.getInfinite?input={encoded_input}"
        
        logger.info(f"Fetching images for user {username}{' with cursor' if cursor else ''}")
        
        try:
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            # Extract the data (handles both standard and devalue formats)
            parsed = self._parse_trpc_data(result)
            if not parsed or not isinstance(parsed, dict):
                parsed = {}
            items = parsed.get('items', [])
            next_cursor = parsed.get('nextCursor')
            
            return {
                "items": items,
                "nextCursor": next_cursor
            }
        except Exception as e:
            logger.error(f"Error fetching images for user {username}: {e}")
            return {"items": [], "nextCursor": None}

    def get_all_images_by_username(self, username):
        """Get all images for a user by handling pagination."""
        all_images = []
        cursor = None
        
        logger.info(f"Starting retrieval of all images for user {username}")
        
        while True:
            result = self.get_images_by_username(username, cursor)
            if not result or not result.get("items"):
                break
                
            all_images.extend(result.get("items", []))
            cursor = result.get("nextCursor")
            
            if not cursor:
                break
        
        logger.info(f"Retrieved a total of {len(all_images)} images for user {username}")
        return all_images

    def get_my_collections(self):
        """Get the authenticated user's collections via the official TRPC API.

        Uses the `collection.getAllUser` endpoint, which is a protected query
        that returns all of the authenticated user's collections. This replaces
        the previous HTML-scraping approach that broke due to 403 Forbidden
        bot protection on the /collections page.
        """
        logger.info("Fetching user collections via TRPC API (collection.getAllUser)")

        # All fields in getAllUserCollectionsInputSchema are optional, so an
        # empty json object returns every collection owned/contributed by the
        # authenticated user.
        request_data = {"json": {}}
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/collection.getAllUser?input={encoded_input}"

        try:
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()

            collections = result.get("result", {}).get("data", {}).get("json", [])
            if not isinstance(collections, list):
                collections = []

            if not collections:
                logger.warning("No collections found.")
                return []

            # Ensure expected fields exist for UI consistency
            for item in collections:
                if 'type' not in item:
                    item['type'] = 'Collection'
                if 'image' not in item:
                    item['image'] = None
                if 'nsfw' not in item:
                    item['nsfw'] = False

            logger.info(f"Found {len(collections)} collections via TRPC API.")
            return collections

        except Exception as e:
            logger.error(f"Error fetching user collections: {e}")
            return []

    def add_image_to_collection(self, image_id, collection_id):
        """Add an image to a collection."""
        request_data = {
            "json": {
                "imageId": int(image_id),
                "collections": [
                    {"collectionId": int(collection_id)}
                ]
            }
        }
        
        url = f"{self.BASE_URL}/collection.saveItem"
        
        try:
            # POST request for saveItem
            response = requests.post(url, json=request_data, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            return True
        except Exception as e:
            if 'response' in locals() and response is not None:
                 logger.error(f"Error details: {response.text}")
            logger.error(f"Error adding image {image_id} to collection {collection_id}: {e}")
            return False

    def remove_image_from_collection(self, image_id, collection_id):
        """Remove an image from a collection."""
        request_data = {
            "json": {
                "collectionId": int(collection_id),
                "itemId": int(image_id)
            }
        }
        
        url = f"{self.BASE_URL}/collection.removeFromCollection"
        
        try:
            # POST request for removeFromCollection
            response = requests.post(url, json=request_data, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            return True
        except Exception as e:
            if 'response' in locals() and response is not None:
                 logger.error(f"Error details: {response.text}")
            logger.error(f"Error removing image {image_id} from collection {collection_id}: {e}")
            return False

    
    def get_image_details(self, image_id):
        """Get detailed information about an image or video."""
        logger.info(f"Fetching details for media ID: {image_id}")
        
        # Create request data
        request_data = {
            "json": {
                "id": int(image_id),
                "authed": True
            }
        }
        
        # Encode parameters
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/image.get?input={encoded_input}"
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            return result.get("result", {}).get("data", {}).get("json")
        except Exception as e:
            logger.error(f"Error fetching image details {image_id}: {e}")
            return None
    
    def get_image_generation_data(self, image_id):
        """Get generation data for an image (prompts, models used, etc.)."""
        logger.info(f"Fetching generation data for media ID: {image_id}")
        
        # Create request data
        request_data = {
            "json": {
                "id": int(image_id),
                "authed": True
            }
        }
        
        # Encode parameters
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/image.getGenerationData?input={encoded_input}"
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            return result.get("result", {}).get("data", {}).get("json")
        except Exception as e:
            logger.error(f"Error fetching generation data {image_id}: {e}")
            return None
    
    def get_image_tags(self, image_id):
        """Get tags for an image."""
        logger.info(f"Fetching tags for media ID: {image_id}")
        
        # Create request data
        request_data = {
            "json": {
                "id": int(image_id),
                "type": "image",
                "authed": True
            }
        }
        
        # Encode parameters
        encoded_input = quote(json.dumps(request_data, separators=(',', ':')))
        url = f"{self.BASE_URL}/tag.getVotableTags?input={encoded_input}"
        
        try:
            # Make direct request with authorization header and proxy
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies())
            response.raise_for_status()
            result = response.json()
            
            return result.get("result", {}).get("data", {}).get("json")
        except Exception as e:
            logger.error(f"Error fetching tags {image_id}: {e}")
            return []

    def get_model_by_id(self, model_id):
        """Get model details via REST API: GET /api/v1/models/:modelId."""
        logger.info(f"Fetching model with ID: {model_id}")
        url = f"{get_site_base_url()}/api/v1/models/{int(model_id)}"
        try:
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching model {model_id}: {e}")
            if 'response' in locals() and response is not None:
                logger.error(f"Response: {response.text[:500]}")
            return None

    def get_model_version_by_id(self, version_id):
        """Get model version details via REST API: GET /api/v1/model-versions/:id."""
        logger.info(f"Fetching model version with ID: {version_id}")
        url = f"{get_site_base_url()}/api/v1/model-versions/{int(version_id)}"
        try:
            response = requests.get(url, headers=self.headers, proxies=config.get_proxies(), timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching model version {version_id}: {e}")
            return None

def parse_model_input(value):
    """Parse model ID or version ID from plain ID / URL.

    Supports:
    - 12345
    - https://civitai.com/models/12345
    - https://civitai.com/models/12345/model-name
    - https://civitai.com/models/12345?modelVersionId=67890
    - https://civitai.red/models/12345
    """
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None

    version_id = None
    model_id = None

    # Query modelVersionId
    m_ver = re.search(r'[?&]modelVersionId=(\d+)', text, re.IGNORECASE)
    if m_ver:
        version_id = int(m_ver.group(1))

    # Path /models/{id}
    m_model = re.search(r'(?:civitai\.(?:com|red)/)?models/(\d+)', text, re.IGNORECASE)
    if m_model:
        model_id = int(m_model.group(1))
    elif re.fullmatch(r'\d+', text):
        model_id = int(text)

    return model_id, version_id

def extract_metadata(api, image_data):
    """Extract metadata from image data and related API responses."""
    image_id = image_data.get("id")
    
    # Basic metadata
    # Check for video URL if it exists (common for videos)
    original_url = image_data.get("url")
    url = original_url
    
    if image_data.get("type") == "video" and "videoUrl" in image_data and image_data["videoUrl"]:
        url = image_data["videoUrl"]
    elif "videoUrl" in image_data and image_data["videoUrl"]:
        # Fallback if type is not explicitly set but videoUrl exists
        url = image_data["videoUrl"]

    metadata = {
        "id": image_id,
        "name": image_data.get("name"),
        "width": image_data.get("width"),
        "height": image_data.get("height"),
        "mimeType": image_data.get("mimeType"),
        "hash": image_data.get("hash"),
        "nsfw_level": image_data.get("nsfwLevel"),
        "created_at": image_data.get("createdAt"),
        "published_at": image_data.get("publishedAt"),
        "url": url,
        "preview_url": original_url,
        "user": None,
        "stats": None,
        "generation_data": None,
        "tags": []
    }
    
    # Add user info if available
    if "user" in image_data and image_data["user"]:
        metadata["user"] = {
            "id": image_data["user"].get("id"),
            "username": image_data["user"].get("username")
        }
    
    # Add stats if available
    if "stats" in image_data and image_data["stats"]:
        metadata["stats"] = image_data["stats"]
    
    # Fetch additional metadata
    try:
        # Get generation data (prompts, models used, etc.)
        gen_data = api.get_image_generation_data(image_id)
        if gen_data:
            metadata["generation_data"] = gen_data
            
            # Extract prompts if available
            if gen_data.get("meta") and "prompt" in gen_data["meta"]:
                metadata["prompt"] = gen_data["meta"]["prompt"]
            if gen_data.get("meta") and "negativePrompt" in gen_data["meta"]:
                metadata["negative_prompt"] = gen_data["meta"]["negativePrompt"]
            
            # Extract model information if available
            if gen_data.get("resources"):
                metadata["models"] = gen_data["resources"]
        
        # Get tags
        tags = api.get_image_tags(image_id)
        if tags:
            metadata["tags"] = [{"id": tag.get("id"), "name": tag.get("name")} for tag in tags]
    
    except Exception as e:
        logger.error(f"Error fetching additional metadata for media {image_id}: {e}")
    
    return metadata

def create_collection_metadata(api, collection_id, images_metadata):
    """Create a metadata object for a collection."""
    collection = api.get_collection_by_id(collection_id)
    if not collection:
        logger.error(f"Failed to get collection data for ID: {collection_id}")
        return {
            "id": collection_id,
            "name": f"Collection-{collection_id}",
            "media_count": len(images_metadata),
            "media": images_metadata
        }
    
    # Extract collection data from the response
    collection_data = collection.get("collection", {})
    
    collection_meta = {
        "id": collection_data.get("id", collection_id),
        "name": collection_data.get("name", f"Collection-{collection_id}"),
        "description": collection_data.get("description", ""),
        "type": collection_data.get("type"),
        "nsfw": collection_data.get("nsfw"),
        "nsfwLevel": collection_data.get("nsfwLevel"),
        "created_at": collection_data.get("createdAt"),
        "user": {
            "id": collection_data.get("user", {}).get("id"),
            "username": collection_data.get("user", {}).get("username")
        },
        "media_count": len(images_metadata),
        "media": images_metadata
    }
    
    return collection_meta