"""
Morpheus Model Management Node - Native ComfyUI Gallery Implementation
A ComfyUI custom node for browsing and selecting talent models with gallery interface
"""

import os
import json
import uuid
from PIL import Image
import torch
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
# Conditional imports for ComfyUI environment
try:
    import server
    from aiohttp import web
    COMFYUI_AVAILABLE = True
except ImportError:
    # Mock objects for development environment
    server = None
    web = None
    COMFYUI_AVAILABLE = False

from .schema import CatalogManager, create_sample_catalog
from .config import (
    SUPABASE_URL, SUPABASE_ANON_KEY, 
    CATALOG_JSON_URL, CATALOG_BASE_URL, IMAGES_BASE_URL, THUMBNAILS_BASE_URL,
    LICENSE_CACHE_DAYS, LICENSE_OFFLINE_GRACE_DAYS,
    PATREON_CLIENT_ID, PATREON_CLIENT_SECRET, PATREON_CREATOR_ACCESS_TOKEN,
    PATREON_REDIRECT_URI, PATREON_AUTHORIZE_URL, PATREON_TOKEN_URL, PATREON_API_URL,
    SUPABASE_FUNCTIONS_URL
)
from datetime import datetime, timedelta
import urllib.request
import urllib.error
import urllib.parse

# Node directory for file paths
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_STATE_FILE = os.path.join(NODE_DIR, "morpheus_ui_state.json")
LICENSE_CACHE_FILE = os.path.join(NODE_DIR, ".license_cache.json")
PATREON_AUTH_FILE = os.path.join(NODE_DIR, ".patreon_auth.json")
REMOTE_CATALOG_CACHE = os.path.join(NODE_DIR, ".remote_catalog_cache.json")
DEVICE_ID_FILE = os.path.join(NODE_DIR, ".device_id")

def get_or_create_device_id() -> str:
    """Get or create a unique device ID for Patreon OAuth authentication"""
    if os.path.exists(DEVICE_ID_FILE):
        try:
            with open(DEVICE_ID_FILE, 'r') as f:
                device_id = f.read().strip()
                if device_id:
                    return device_id
        except:
            pass
    
    # Generate new device ID
    device_id = str(uuid.uuid4())
    try:
        with open(DEVICE_ID_FILE, 'w') as f:
            f.write(device_id)
    except:
        pass
    
    return device_id

# Supabase client for license validation (using built-in config)
supabase_client = None
try:
    from supabase import create_client
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("Morpheus: Connected to remote catalog server")
    else:
        print("Morpheus: Remote catalog not configured")
except ImportError:
    print("Morpheus: Supabase library not installed - using local catalog only")
except Exception as e:
    print(f"Morpheus: Failed to connect to remote server: {e}")

def fetch_remote_catalog() -> dict:
    """Fetch catalog.json from Supabase Storage"""
    try:
        with urllib.request.urlopen(CATALOG_JSON_URL, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            # Cache locally for offline use
            try:
                with open(REMOTE_CATALOG_CACHE, 'w', encoding='utf-8') as f:
                    json.dump({'fetched_at': datetime.now().isoformat(), 'catalog': data}, f)
            except:
                pass
            return data
    except Exception as e:
        print(f"Morpheus: Failed to fetch remote catalog: {e}")
        # Try cached version
        if os.path.exists(REMOTE_CATALOG_CACHE):
            try:
                with open(REMOTE_CATALOG_CACHE, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    return cached.get('catalog', {})
            except:
                pass
        return None

def validate_license(license_key: str, email: str) -> dict:
    """Validate license with Supabase, with local caching (7-day revalidation)"""
    if not license_key or not email:
        return {"valid": False, "error": "License key and email required"}
    
    # Check local cache first
    if os.path.exists(LICENSE_CACHE_FILE):
        try:
            with open(LICENSE_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            if cache.get('license_key') == license_key and cache.get('email') == email:
                last_validated = datetime.fromisoformat(cache.get('last_validated', '2000-01-01'))
                if datetime.now() - last_validated < timedelta(days=LICENSE_CACHE_DAYS):
                    if cache.get('is_active', False):
                        return {"valid": True, "cached": True}
        except Exception as e:
            print(f"Morpheus: Cache read error: {e}")
    
    # Online validation required - check if Supabase is available
    if not supabase_client:
        # If no Supabase configured, check if we have a still-valid cache (within grace period)
        if os.path.exists(LICENSE_CACHE_FILE):
            try:
                with open(LICENSE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                if cache.get('license_key') == license_key and cache.get('email') == email and cache.get('is_active'):
                    last_validated = datetime.fromisoformat(cache.get('last_validated', '2000-01-01'))
                    if datetime.now() - last_validated < timedelta(days=LICENSE_OFFLINE_GRACE_DAYS):
                        return {"valid": True, "cached": True, "warning": "Offline mode - using cached license"}
                    else:
                        return {"valid": False, "error": "License cache expired - online validation required"}
            except:
                pass
        return {"valid": False, "error": "License server not configured"}
    
    try:
        response = supabase_client.table('licenses').select('*').eq('license_key', license_key).eq('email', email).eq('is_active', True).execute()
        
        if response.data and len(response.data) > 0:
            # Valid license - update cache
            cache_data = {
                'license_key': license_key,
                'email': email,
                'is_active': True,
                'last_validated': datetime.now().isoformat()
            }
            try:
                with open(LICENSE_CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f)
            except Exception as e:
                print(f"Morpheus: Cache write error: {e}")
            
            # Update last_validated_at in database
            try:
                supabase_client.table('licenses').update({'last_validated_at': datetime.now().isoformat()}).eq('license_key', license_key).execute()
            except:
                pass
            
            return {"valid": True, "cached": False}
        else:
            return {"valid": False, "error": "Invalid license key or email"}
    except Exception as e:
        # Network error - try cached license but enforce grace period limit
        if os.path.exists(LICENSE_CACHE_FILE):
            try:
                with open(LICENSE_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                if cache.get('license_key') == license_key and cache.get('email') == email and cache.get('is_active'):
                    last_validated = datetime.fromisoformat(cache.get('last_validated', '2000-01-01'))
                    if datetime.now() - last_validated < timedelta(days=LICENSE_OFFLINE_GRACE_DAYS):
                        return {"valid": True, "cached": True, "warning": "Offline mode - using cached license"}
                    else:
                        return {"valid": False, "error": "License cache expired - online validation required"}
            except:
                pass
        return {"valid": False, "error": f"License validation failed: {str(e)}"}

# Helper functions for JSON state management
def load_json_file(file_path, default_data={}):
    if not os.path.exists(file_path):
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                return default_data
            return json.loads(content)
    except Exception as e:
        print(f"Morpheus: Error loading {file_path}: {e}")
        return default_data

def save_json_file(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Morpheus: Error saving {file_path}: {e}")

load_ui_state = lambda: load_json_file(UI_STATE_FILE)
save_ui_state = lambda data: save_json_file(data, UI_STATE_FILE)

def filter_remote_talents(talents: List[Dict], filters: Dict) -> List[Dict]:
    """Filter talents from remote catalog using the same logic as local catalog"""
    filter_name = filters.get('name_filter', '').lower()
    filter_tags = filters.get('tag_filter', [])
    filter_logic = filters.get('tag_logic', 'OR').upper()
    filter_gender = filters.get('gender')
    filter_age_group = filters.get('age_group')
    filter_ethnicity = filters.get('ethnicity')
    filter_favorites_only = filters.get('favorites_only', False)
    
    filtered = []
    for talent in talents:
        # Name filter
        if filter_name and filter_name not in talent.get('name', '').lower():
            continue
        
        # Gender filter
        if filter_gender and talent.get('gender', '') != filter_gender:
            continue
        
        # Age group filter
        if filter_age_group and talent.get('age_group', '') != filter_age_group:
            continue
        
        # Ethnicity filter
        if filter_ethnicity and talent.get('ethnicity', '') != filter_ethnicity:
            continue
        
        # Favorites filter
        if filter_favorites_only and not talent.get('is_favorite', False):
            continue
        
        # Tag filter
        if filter_tags:
            talent_tags = [t.lower() for t in talent.get('tags', [])]
            if filter_logic == 'AND':
                if not all(tag in talent_tags for tag in filter_tags):
                    continue
            else:  # OR logic
                if not any(tag in talent_tags for tag in filter_tags):
                    continue
        
        filtered.append(talent)
    
    return filtered

def paginate_talents(talents: List[Dict], page: int, page_size: int = 20) -> Tuple[List[Dict], int, int]:
    """Paginate talents with special handling for page 1 (upload card + 7 talents)"""
    total_talents = len(talents)
    
    if total_talents <= 7:
        total_pages = 1
    else:
        remaining_talents = total_talents - 7
        additional_pages = (remaining_talents + page_size - 1) // page_size
        total_pages = 1 + additional_pages
    
    if page == 1:
        start_index = 0
        end_index = min(7, total_talents)
    else:
        start_index = 7 + (page - 2) * page_size
        end_index = min(start_index + page_size, total_talents)
    
    return talents[start_index:end_index], total_pages, total_talents

def add_remote_image_urls(talents: List[Dict]) -> None:
    """Add thumbnail_url and full_image_url for talents with remote image URLs"""
    for talent in talents:
        image_path = talent.get('image_path', '')
        if image_path:
            if image_path.startswith('http'):
                talent['thumbnail_url'] = image_path
                talent['full_image_url'] = image_path
            else:
                # Build full URL from relative path
                full_url = f"{CATALOG_BASE_URL}/{image_path}"
                talent['thumbnail_url'] = full_url
                talent['full_image_url'] = full_url
                talent['image_path'] = full_url

MINIMUM_TIER_CENTS = 1500  # 15€ = R&D Insider tier minimum
CREATOR_BYPASS_NAMES = ["Sergio Valsecchi"]  # Campaign creators get automatic access

async def check_patreon_auth_status(device_id: str) -> dict:
    """Check Patreon authentication status via Supabase Edge Function
    
    Access is granted to:
    - Campaign creators (bypass)
    - Patrons with R&D Insider (15€) or Lab Access (100€) tiers
    Supporter tier (5€) does NOT have catalog access.
    """
    if not device_id:
        return {"authenticated": False, "error": "No device ID"}
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"{SUPABASE_FUNCTIONS_URL}/patreon-status?device_id={device_id}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    is_authenticated = data.get("authenticated", False)
                    is_patron = data.get("is_patron", False)
                    entitled_cents = data.get("entitled_cents", 0)
                    user_name = data.get("user_name", "")
                    
                    # Check if user is campaign creator (bypass tier requirement)
                    is_creator = user_name in CREATOR_BYPASS_NAMES
                    
                    # Check if patron has minimum tier (R&D Insider = 15€ or Lab Access = 100€)
                    has_tier_access = is_patron and entitled_cents >= MINIMUM_TIER_CENTS
                    
                    # Grant access to creators OR patrons with sufficient tier
                    has_catalog_access = is_authenticated and (is_creator or has_tier_access)
                    
                    return {
                        "authenticated": has_catalog_access,
                        "user": user_name,
                        "is_patron": is_patron,
                        "is_creator": is_creator,
                        "entitled_cents": entitled_cents,
                        "tier_requirement": MINIMUM_TIER_CENTS,
                        "tier_met": has_tier_access or is_creator
                    }
                else:
                    return {"authenticated": False, "error": f"Status check failed: {response.status}"}
    except Exception as e:
        print(f"Morpheus: Patreon auth check failed: {e}")
        return {"authenticated": False, "error": str(e)}

# Remote Image Cache Manager
REMOTE_IMAGE_CACHE_DIR = os.path.join(NODE_DIR, "cache", "remote_images")

def ensure_cache_dir():
    """Ensure the remote image cache directory exists"""
    if not os.path.exists(REMOTE_IMAGE_CACHE_DIR):
        os.makedirs(REMOTE_IMAGE_CACHE_DIR, exist_ok=True)

def get_cached_image_path(talent_id: str) -> str:
    """Get the local cache path for a talent image"""
    ensure_cache_dir()
    return os.path.join(REMOTE_IMAGE_CACHE_DIR, f"{talent_id}.jpg")

def is_image_cached(talent_id: str) -> bool:
    """Check if an image is already cached locally"""
    cache_path = get_cached_image_path(talent_id)
    return os.path.exists(cache_path)

async def download_remote_image(talent_id: str, image_url: str, semaphore) -> Optional[str]:
    """Download a single remote image to local cache with semaphore limiting"""
    if not image_url:
        return None
    
    cache_path = get_cached_image_path(talent_id)
    
    # Return cached path if already exists
    if os.path.exists(cache_path):
        return cache_path
    
    async with semaphore:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(cache_path, 'wb') as f:
                            f.write(content)
                        print(f"Morpheus: Cached image for {talent_id}")
                        return cache_path
                    else:
                        print(f"Morpheus: Failed to download image for {talent_id}: HTTP {response.status}")
                        return None
        except Exception as e:
            print(f"Morpheus: Error downloading image for {talent_id}: {e}")
            return None

async def download_page_images(talents: List[Dict]) -> Dict[str, str]:
    """Download images for a page of talents with parallel downloads (max 4 concurrent)"""
    import asyncio
    
    ensure_cache_dir()
    semaphore = asyncio.Semaphore(4)  # Max 4 parallel downloads
    
    # Create download tasks for talents that need images
    tasks = []
    talent_ids = []
    for talent in talents:
        talent_id = talent.get('id', '')
        image_url = talent.get('image_path') or talent.get('full_image_url') or talent.get('thumbnail_url')
        if talent_id and image_url:
            tasks.append(download_remote_image(talent_id, image_url, semaphore))
            talent_ids.append(talent_id)
    
    # Execute all downloads in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build result dict
    cached_paths = {}
    for i, result in enumerate(results):
        if isinstance(result, str) and result:
            cached_paths[talent_ids[i]] = result
    
    return cached_paths

def get_cached_image_or_url(talent_id: str, image_url: str) -> str:
    """Get local cached path if exists, otherwise return original URL"""
    cache_path = get_cached_image_path(talent_id)
    if os.path.exists(cache_path):
        return cache_path
    return image_url

def load_cached_image_as_tensor(talent_id: str) -> Optional[torch.Tensor]:
    """Load a cached image and convert to PyTorch tensor for ComfyUI output"""
    cache_path = get_cached_image_path(talent_id)
    
    if not os.path.exists(cache_path):
        return None
    
    try:
        # Load image with PIL
        img = Image.open(cache_path)
        img = img.convert('RGB')
        
        # Convert to numpy array
        img_array = np.array(img).astype(np.float32) / 255.0
        
        # Convert to tensor with shape [1, H, W, C] (batch, height, width, channels)
        tensor = torch.from_numpy(img_array).unsqueeze(0)
        
        return tensor
    except Exception as e:
        print(f"Morpheus: Error loading cached image {talent_id}: {e}")
        return None

# Safe route registration function
def register_routes():
    """Register API endpoints only when ComfyUI server is available"""
    if not COMFYUI_AVAILABLE or not server:
        return
    
    @server.PromptServer.instance.routes.get("/morpheus/device_id")
    async def get_device_id_endpoint(request):
        """Endpoint to get or generate a unique device ID for Patreon OAuth"""
        try:
            device_id = get_or_create_device_id()
            return web.json_response({"device_id": device_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/remote_talents")
    async def get_remote_talents_endpoint(request):
        """Endpoint to get talents from remote Supabase catalog (no local files needed)"""
        try:
            # Get filter parameters
            filter_tags_str = request.query.get('tags', '').strip().lower()
            filter_tags = [tag.strip() for tag in filter_tags_str.split(',') if tag.strip()]
            
            filters = {
                "name_filter": request.query.get('name', '').strip().lower(),
                "tag_filter": filter_tags,
                "tag_logic": request.query.get('logic', 'OR').upper(),
                "gender": request.query.get('gender', '').strip() or None,
                "age_group": request.query.get('age_group', '').strip() or None,
                "ethnicity": request.query.get('ethnicity', '').strip() or None,
                "favorites_only": request.query.get('favorites_only', '').lower() == 'true',
            }
            
            page = int(request.query.get('page', 1))
            page_size = int(request.query.get('page_size', 20))
            
            # Fetch remote catalog
            catalog_data = fetch_remote_catalog()
            if not catalog_data:
                return web.json_response({
                    "error": "Failed to fetch remote catalog",
                    "talents": [],
                    "total_pages": 0,
                    "current_page": 1,
                    "total_count": 0
                }, status=503)
            
            # Apply filters using shared helper
            filtered_talents = filter_remote_talents(catalog_data.get("talents", []), filters)
            
            # Add remote image URLs
            add_remote_image_urls(filtered_talents)
            
            # Paginate using shared helper
            paginated_talents, total_pages, total_count = paginate_talents(filtered_talents, page, page_size)
            
            return web.json_response({
                "talents": paginated_talents,
                "total_pages": total_pages,
                "current_page": page,
                "total_count": total_count,
                "source": "remote"
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in get_remote_talents_endpoint: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/talents")
    async def get_talents_endpoint(request):
        try:
            # Check if remote catalog is requested
            use_remote = request.query.get('use_remote', 'false').lower() == 'true'
            
            # For remote mode, check Patreon authentication first
            if use_remote:
                device_id = request.query.get('device_id', '')
                if not device_id:
                    # Try to get device_id from cookie or generate new one
                    device_id = get_or_create_device_id()
                
                auth_status = await check_patreon_auth_status(device_id)
                
                if not auth_status.get("authenticated", False):
                    # Not authenticated - return empty response with show_cta flag
                    return web.json_response({
                        "authenticated": False,
                        "talents": [],
                        "total_pages": 0,
                        "current_page": 1,
                        "total_count": 0,
                        "show_cta": True,
                        "source": "remote"
                    })
            
            # Get query parameters
            filter_name = request.query.get('name', '').strip().lower()
            filter_tags_str = request.query.get('tags', '').strip().lower()
            filter_tags = [tag.strip() for tag in filter_tags_str.split(',') if tag.strip()]
            filter_logic = request.query.get('logic', 'OR').upper()
            filter_gender = request.query.get('gender', '').strip()
            filter_age_group = request.query.get('age_group', '').strip()
            filter_ethnicity = request.query.get('ethnicity', '').strip()
            filter_favorites_only = request.query.get('favorites_only', '').lower() == 'true'
            
            page = int(request.query.get('page', 1))
            page_size = int(request.query.get('page_size', 20))
            
            catalog_path = request.query.get('catalog_path', '')
            images_folder = request.query.get('images_folder', '')
            
            # For remote mode, we don't need local paths
            if use_remote:
                catalog_data = fetch_remote_catalog()
                if not catalog_data:
                    return web.json_response({"error": "Failed to fetch remote catalog"}, status=503)
            else:
                if not catalog_path or not images_folder:
                    return web.json_response({"error": "Missing catalog_path or images_folder"}, status=400)
                
                # Resolve paths relative to node directory
                if not os.path.isabs(catalog_path):
                    catalog_path = os.path.join(NODE_DIR, catalog_path)
                if not os.path.isabs(images_folder):
                    images_folder = os.path.join(NODE_DIR, images_folder)
                
                # Initialize catalog manager
                manager = CatalogManager(catalog_path)
                catalog_data = manager.load_catalog()
                
                if not catalog_data:
                    catalog_data = create_sample_catalog()
                    try:
                        manager.save_catalog(catalog_data)
                    except:
                        pass
            
            # Build filters dict
            filters = {
                "name_filter": filter_name,
                "tag_filter": filter_tags,
                "tag_logic": filter_logic,
                "gender": filter_gender if filter_gender else None,
                "age_group": filter_age_group if filter_age_group else None,
                "ethnicity": filter_ethnicity if filter_ethnicity else None,
                "favorites_only": filter_favorites_only,
            }
            
            if use_remote:
                # Use shared helper for remote filtering
                filtered_talents = filter_remote_talents(catalog_data.get("talents", []), filters)
                # Add remote image URLs
                add_remote_image_urls(filtered_talents)
            else:
                manager = CatalogManager(catalog_path)
                filtered_talents = manager.filter_talents(catalog_data.get("talents", []), filters)
                # Add local image URLs
                for talent in filtered_talents:
                    talent_id = talent.get('id', '')
                    image_path = talent.get('image_path', '')
                    if image_path and image_path.startswith('http'):
                        talent['thumbnail_url'] = image_path
                        talent['full_image_url'] = image_path
                    elif talent_id:
                        talent['thumbnail_url'] = f"/morpheus/thumbnail/{talent_id}?catalog_path={catalog_path}&images_folder={images_folder}"
                        talent['full_image_url'] = f"/morpheus/image/{talent_id}?catalog_path={catalog_path}&images_folder={images_folder}"
            
            # Paginate using shared helper
            paginated_talents, total_pages, total_count = paginate_talents(filtered_talents, page, page_size)
            
            response_data = {
                "talents": paginated_talents,
                "total_pages": total_pages,
                "current_page": page,
                "total_count": total_count,
                "source": "remote" if use_remote else "local"
            }
            
            # Add authenticated flag for remote mode
            if use_remote:
                response_data["authenticated"] = True
            
            return web.json_response(response_data)
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in get_talents_endpoint: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/thumbnail/{talent_id}")
    async def get_thumbnail(request):
        talent_id = request.match_info.get('talent_id')
        
        # Enhanced path security validation
        if not talent_id:
            return web.Response(status=400)
        
        # Normalize and validate talent_id to prevent path traversal
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', talent_id):
            return web.Response(status=403)
        
        try:
            catalog_path = request.query.get('catalog_path', '')
            images_folder = request.query.get('images_folder', '')
            
            if not catalog_path or not images_folder:
                return web.Response(status=400)
            
            # Normalize paths to prevent traversal attacks
            catalog_path = os.path.normpath(catalog_path)
            images_folder = os.path.normpath(images_folder)
            
            # Ensure paths don't escape the node directory
            if '..' in catalog_path or '..' in images_folder:
                return web.Response(status=403)
            
            # Check for thumbnails directory
            thumbnails_dir = os.path.join(os.path.dirname(catalog_path), '.thumbnails')
            thumbnail_path = os.path.join(thumbnails_dir, f"{talent_id}_thumb.jpg")
            
            # Ensure thumbnail path is safe
            thumbnail_path = os.path.normpath(thumbnail_path)
            if os.path.exists(thumbnail_path):
                return web.FileResponse(thumbnail_path)
            
            # If no thumbnail, try to serve original image
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            talent = next((t for t in catalog_data.get('talents', []) if t['id'] == talent_id), None)
            if not talent:
                return web.Response(status=404)
            
            # Try to find the original image
            image_path = talent.get('image_path', '')
            if image_path:
                # Normalize image path for security
                image_path = os.path.normpath(image_path)
                if '..' in image_path:
                    return web.Response(status=403)
                
                full_image_path = os.path.join(os.path.dirname(catalog_path), image_path)
                full_image_path = os.path.normpath(full_image_path)
                
                if os.path.exists(full_image_path):
                    return web.FileResponse(full_image_path)
            
            return web.Response(status=404)
            
        except Exception as e:
            print(f"Morpheus: Error serving thumbnail {talent_id}: {e}")
            return web.Response(status=500)

    @server.PromptServer.instance.routes.get("/morpheus/image/{talent_id}")
    async def get_full_image(request):
        """Endpoint to serve ONLY full-size original images (never thumbnails)"""
        talent_id = request.match_info.get('talent_id')
        
        # Enhanced path security validation
        if not talent_id:
            return web.Response(status=400)
        
        # Normalize and validate talent_id to prevent path traversal
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', talent_id):
            return web.Response(status=403)
        
        try:
            catalog_path = request.query.get('catalog_path', '')
            images_folder = request.query.get('images_folder', '')
            
            if not catalog_path or not images_folder:
                return web.Response(status=400)
            
            # Normalize paths to prevent traversal attacks
            catalog_path = os.path.normpath(catalog_path)
            images_folder = os.path.normpath(images_folder)
            
            # Ensure paths don't escape the node directory
            if '..' in catalog_path or '..' in images_folder:
                return web.Response(status=403)
            
            # Load catalog and find talent
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            talent = next((t for t in catalog_data.get('talents', []) if t['id'] == talent_id), None)
            if not talent:
                return web.Response(status=404)
            
            # Serve ONLY the original image (never thumbnail)
            image_path = talent.get('image_path', '')
            if image_path:
                # Normalize image path for security
                image_path = os.path.normpath(image_path)
                if '..' in image_path:
                    return web.Response(status=403)
                
                full_image_path = os.path.join(os.path.dirname(catalog_path), image_path)
                full_image_path = os.path.normpath(full_image_path)
                
                if os.path.exists(full_image_path):
                    return web.FileResponse(full_image_path)
            
            return web.Response(status=404)
            
        except Exception as e:
            print(f"Morpheus: Error serving full image {talent_id}: {e}")
            return web.Response(status=500)

    @server.PromptServer.instance.routes.post("/morpheus/upload")
    async def upload_talent_image(request):
        """Upload talent image file"""
        try:
            reader = await request.multipart()
            field = await reader.next()
            
            if field.name != 'image':
                return web.json_response({"error": "Expected 'image' field"}, status=400)
            
            # Read file data
            filename = field.filename
            if not filename:
                return web.json_response({"error": "No filename provided"}, status=400)
            
            # Validate file extension
            allowed_extensions = {'.jpg', '.jpeg', '.png'}
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in allowed_extensions:
                return web.json_response({"error": "Only JPG and PNG files are allowed"}, status=400)
            
            # Create temp directory if it doesn't exist
            temp_dir = os.path.join(NODE_DIR, '.temp_uploads')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate unique temp filename
            import uuid
            temp_filename = f"temp_{uuid.uuid4().hex}{file_ext}"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            # Save uploaded file
            with open(temp_path, 'wb') as f:
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            
            return web.json_response({
                "status": "success",
                "temp_filename": temp_filename,
                "original_filename": filename
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in upload_talent_image: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/morpheus/save_talent")
    async def save_talent_metadata(request):
        """Save talent with metadata to catalog"""
        try:
            data = await request.json()
            
            # Validate required fields
            required_fields = ['temp_filename', 'name', 'gender', 'age_group', 'ethnicity']
            for field in required_fields:
                if not data.get(field):
                    return web.json_response({"error": f"Missing required field: {field}"}, status=400)
            
            # Generate unique talent ID
            import uuid
            import re
            talent_name = data['name']
            base_id = re.sub(r'[^a-zA-Z0-9_]', '_', talent_name.lower())
            talent_id = f"{base_id}_{uuid.uuid4().hex[:8]}"
            
            # Move temp file to images directory
            temp_dir = os.path.join(NODE_DIR, '.temp_uploads')
            temp_path = os.path.join(temp_dir, data['temp_filename'])
            
            if not os.path.exists(temp_path):
                return web.json_response({"error": "Temp file not found"}, status=404)
            
            # Determine final image filename with duplicate check
            images_dir = os.path.join(NODE_DIR, 'catalog', 'images')
            os.makedirs(images_dir, exist_ok=True)
            
            file_ext = os.path.splitext(data['temp_filename'])[1]
            base_filename = f"{talent_id}{file_ext}"
            final_filename = base_filename
            final_path = os.path.join(images_dir, final_filename)
            
            # Check for duplicates and modify filename if needed
            counter = 1
            while os.path.exists(final_path):
                name_part = talent_id
                final_filename = f"{name_part}_{counter}{file_ext}"
                final_path = os.path.join(images_dir, final_filename)
                counter += 1
            
            # Move file from temp to final location
            import shutil
            shutil.move(temp_path, final_path)
            
            # Create talent entry
            talent_entry = {
                "id": talent_id,
                "name": data['name'],
                "gender": data['gender'],
                "age_group": data['age_group'],
                "ethnicity": data['ethnicity'],
                "skin_tone": "unknown",  # Could be added to form later
                "hair_color": data.get('hair_color', ''),
                "hair_style": data.get('hair_style', ''),
                "eye_color": data.get('eye_color', ''),
                "body_type": "unknown",  # Could be added to form later
                "freckles": False,  # Could be added to form later
                "tags": data.get('tags', []),
                "description": data.get('description', ''),
                "image_path": f"images/{final_filename}",
                "copyright": "User Upload",
                "download_url": "",
                "rating": 0.0,
                "portfolio_size": 0,
                "is_favorite": False
            }
            
            # Load and update catalog
            catalog_path = os.path.join(NODE_DIR, 'catalog', 'catalog.json')
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            if not catalog_data:
                catalog_data = {
                    "version": "1.0",
                    "description": "Morpheus Model Management Talent Catalog",
                    "created": "2025-09-14",
                    "last_updated": "2025-09-14",
                    "talents": []
                }
            
            # Add new talent to catalog
            catalog_data["talents"].append(talent_entry)
            
            # Update last_updated timestamp
            from datetime import datetime
            catalog_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            
            # Save updated catalog
            manager.save_catalog(catalog_data)
            
            # Generate thumbnail
            try:
                from PIL import Image
                with Image.open(final_path) as img:
                    # Create thumbnail
                    thumbnail_size = (150, 150)
                    img.thumbnail(thumbnail_size, Image.LANCZOS)
                    
                    # Save thumbnail
                    thumbnails_dir = os.path.join(NODE_DIR, 'catalog', '.thumbnails')
                    os.makedirs(thumbnails_dir, exist_ok=True)
                    thumbnail_path = os.path.join(thumbnails_dir, f"{talent_id}_thumb.jpg")
                    
                    # Convert to RGB if needed (for PNG with transparency)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1])
                            img = background
                    
                    img.save(thumbnail_path, 'JPEG', quality=85)
            except Exception as thumb_error:
                print(f"Morpheus: Error generating thumbnail: {thumb_error}")
                # Continue anyway, thumbnail will be generated on demand
            
            return web.json_response({
                "status": "success",
                "talent_id": talent_id,
                "message": "Talent saved successfully"
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in save_talent_metadata: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/morpheus/ui_state")
    async def set_ui_state(request):
        try:
            data = await request.json()
            node_id = str(data.get("node_id"))
            gallery_id = data.get("gallery_id")
            state = data.get("state", {})
            
            if not node_id or not gallery_id:
                return web.json_response({"status": "error", "message": "node_id or gallery_id required"}, status=400)
            
            node_key = f"{gallery_id}_{node_id}"
            ui_states = load_ui_state()
            if node_key not in ui_states:
                ui_states[node_key] = {}
            ui_states[node_key].update(state)
            save_ui_state(ui_states)
            
            return web.json_response({"status": "ok"})
            
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/ui_state")
    async def get_ui_state(request):
        try:
            node_id = request.query.get('node_id')
            gallery_id = request.query.get('gallery_id')
            
            if not node_id or not gallery_id:
                return web.json_response({"error": "node_id or gallery_id required"}, status=400)
            
            node_key = f"{gallery_id}_{node_id}"
            ui_states = load_ui_state()
            node_state = ui_states.get(node_key, {
                "selected_talent_id": "",
                "filters": {
                    "name": "",
                    "tags": "",
                    "logic": "OR",
                    "gender": "",
                    "age_group": "",
                    "ethnicity": ""
                }
            })
            
            return web.json_response(node_state)
            
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/morpheus/favorite")
    async def toggle_favorite(request):
        try:
            data = await request.json()
            talent_id = data.get("talent_id")
            catalog_path = data.get("catalog_path", "catalog/catalog.json")
            
            if not talent_id:
                return web.json_response({"error": "talent_id required"}, status=400)
            
            # Resolve catalog path relative to node directory
            if not os.path.isabs(catalog_path):
                catalog_path = os.path.join(NODE_DIR, catalog_path)
            
            # Initialize catalog manager and load catalog
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            if not catalog_data:
                return web.json_response({"error": "Could not load catalog"}, status=500)
            
            # Find the talent and toggle favorite status
            talent_found = False
            for talent in catalog_data.get("talents", []):
                if talent.get("id") == talent_id:
                    talent_found = True
                    # Toggle is_favorite field
                    current_favorite = talent.get("is_favorite", False)
                    talent["is_favorite"] = not current_favorite
                    break
            
            if not talent_found:
                return web.json_response({"error": "Talent not found"}, status=404)
            
            # Save the updated catalog
            try:
                manager.save_catalog(catalog_data)
                return web.json_response({
                    "status": "success", 
                    "talent_id": talent_id,
                    "is_favorite": talent["is_favorite"]
                })
            except Exception as e:
                return web.json_response({"error": f"Could not save catalog: {str(e)}"}, status=500)
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in toggle_favorite: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/talent/{talent_id}")
    async def get_talent_data(request):
        """Get talent data for editing"""
        try:
            talent_id = request.match_info.get('talent_id')
            
            if not talent_id:
                return web.json_response({"error": "Missing talent_id"}, status=400)
            
            # Validate talent_id format for security
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', talent_id):
                return web.json_response({"error": "Invalid talent_id format"}, status=400)
            
            # Load catalog
            catalog_path = os.path.join(NODE_DIR, 'catalog', 'catalog.json')
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            if not catalog_data:
                return web.json_response({"error": "Catalog not found"}, status=404)
            
            # Find talent by id
            talent = None
            for t in catalog_data.get("talents", []):
                if t.get("id") == talent_id:
                    talent = t
                    break
            
            if not talent:
                return web.json_response({"error": "Talent not found"}, status=404)
            
            return web.json_response({
                "status": "success",
                "talent": talent
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in get_talent_data: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/morpheus/delete_talent")
    async def delete_talent(request):
        """Delete talent from catalog and filesystem"""
        try:
            data = await request.json()
            talent_id = data.get('talent_id')
            
            if not talent_id:
                return web.json_response({"error": "Missing talent_id"}, status=400)
            
            # Validate talent_id format for security
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', talent_id):
                return web.json_response({"error": "Invalid talent_id format"}, status=400)
            
            # Load catalog
            catalog_path = os.path.join(NODE_DIR, 'catalog', 'catalog.json')
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            if not catalog_data:
                return web.json_response({"error": "Catalog not found"}, status=404)
            
            # Find talent to delete (but don't remove from catalog yet)
            talent_to_delete = None
            talent_index = -1
            talents_list = catalog_data.get("talents", [])
            
            for i, talent in enumerate(talents_list):
                if talent.get("id") == talent_id:
                    talent_to_delete = talent
                    talent_index = i
                    break
            
            if not talent_to_delete:
                return web.json_response({"error": "Talent not found"}, status=404)
            
            # Store original catalog for rollback if file deletion fails
            original_catalog = catalog_data.copy()
            
            # Delete image file with robust security checks
            image_path = talent_to_delete.get('image_path', '')
            if image_path:
                # Validate image path for security
                image_path = os.path.normpath(image_path)
                if '..' in image_path or os.path.isabs(image_path):
                    return web.json_response({"error": "Invalid image path detected"}, status=403)
                
                full_image_path = os.path.join(NODE_DIR, 'catalog', image_path)
                
                # Use realpath for symlink-safe path validation
                try:
                    resolved_path = os.path.realpath(full_image_path)
                    expected_dir = os.path.realpath(os.path.join(NODE_DIR, 'catalog', 'images'))
                    
                    # Check path containment using commonpath
                    if os.path.commonpath([resolved_path, expected_dir]) != expected_dir:
                        return web.json_response({"error": "Path outside allowed directory"}, status=403)
                    
                    # Ensure target is a regular file (not directory or symlink)
                    if os.path.exists(resolved_path):
                        if not os.path.isfile(resolved_path) or os.path.islink(full_image_path):
                            return web.json_response({"error": "Invalid file type for deletion"}, status=403)
                        
                        try:
                            os.remove(resolved_path)
                        except Exception as e:
                            return web.json_response({"error": f"Failed to delete image file: {str(e)}"}, status=500)
                        
                except Exception as e:
                    return web.json_response({"error": f"Path validation failed: {str(e)}"}, status=500)
            
            # Delete thumbnail (also with validation)
            thumbnails_dir = os.path.join(NODE_DIR, 'catalog', '.thumbnails')
            thumbnail_path = os.path.join(thumbnails_dir, f"{talent_id}_thumb.jpg")
            if os.path.exists(thumbnail_path):
                try:
                    resolved_thumb = os.path.realpath(thumbnail_path)
                    expected_thumb_dir = os.path.realpath(thumbnails_dir)
                    
                    if os.path.commonpath([resolved_thumb, expected_thumb_dir]) != expected_thumb_dir:
                        return web.json_response({"error": "Thumbnail path security violation"}, status=403)
                    
                    if os.path.isfile(resolved_thumb):
                        os.remove(resolved_thumb)
                except Exception as e:
                    return web.json_response({"error": f"Failed to delete thumbnail: {str(e)}"}, status=500)
            
            # Only now remove from catalog after successful file deletions
            catalog_data["talents"].pop(talent_index)
            
            # Update catalog
            from datetime import datetime
            catalog_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            manager.save_catalog(catalog_data)
            
            return web.json_response({
                "status": "success",
                "message": f"Talent '{talent_to_delete.get('name', talent_id)}' deleted successfully"
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in delete_talent: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/morpheus/update_talent")
    async def update_talent_metadata(request):
        """Update existing talent metadata"""
        try:
            data = await request.json()
            talent_id = data.get('talent_id')
            
            if not talent_id:
                return web.json_response({"error": "Missing talent_id"}, status=400)
            
            # Validate talent_id format for security
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', talent_id):
                return web.json_response({"error": "Invalid talent_id format"}, status=400)
            
            # Validate required fields
            required_fields = ['name', 'gender', 'age_group', 'ethnicity']
            for field in required_fields:
                if not data.get(field):
                    return web.json_response({"error": f"Missing required field: {field}"}, status=400)
            
            # Load catalog
            catalog_path = os.path.join(NODE_DIR, 'catalog', 'catalog.json')
            manager = CatalogManager(catalog_path)
            catalog_data = manager.load_catalog()
            
            if not catalog_data:
                return web.json_response({"error": "Catalog not found"}, status=404)
            
            # Find talent to update
            talent_found = False
            for talent in catalog_data.get("talents", []):
                if talent.get("id") == talent_id:
                    talent_found = True
                    # Update talent fields
                    talent["name"] = data['name']
                    talent["gender"] = data['gender']
                    talent["age_group"] = data['age_group']
                    talent["ethnicity"] = data['ethnicity']
                    talent["hair_color"] = data.get('hair_color', '')
                    talent["hair_style"] = data.get('hair_style', '')
                    talent["eye_color"] = data.get('eye_color', '')
                    talent["tags"] = data.get('tags', [])
                    talent["description"] = data.get('description', '')
                    break
            
            if not talent_found:
                return web.json_response({"error": "Talent not found"}, status=404)
            
            # Update timestamp
            from datetime import datetime
            catalog_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            
            # Save updated catalog
            manager.save_catalog(catalog_data)
            
            return web.json_response({
                "status": "success",
                "message": f"Talent '{data['name']}' updated successfully"
            })
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in update_talent_metadata: {traceback.format_exc()}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/patreon/authorize")
    async def patreon_authorize(request):
        """Redirect user to Patreon OAuth authorization page"""
        try:
            if not PATREON_CLIENT_ID or not PATREON_CLIENT_SECRET:
                return web.json_response({"error": "Patreon OAuth not configured. Missing CLIENT_ID or CLIENT_SECRET."}, status=500)
            
            import secrets
            state = secrets.token_urlsafe(32)
            
            state_file = os.path.join(NODE_DIR, ".patreon_oauth_state.json")
            state_data = {
                "state": state,
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(minutes=10)).isoformat()
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f)
            
            params = {
                "response_type": "code",
                "client_id": PATREON_CLIENT_ID,
                "redirect_uri": PATREON_REDIRECT_URI,
                "scope": "identity identity[email] campaigns.members",
                "state": state
            }
            auth_url = f"{PATREON_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
            
            raise web.HTTPFound(auth_url)
        except web.HTTPFound:
            raise
        except Exception as e:
            print(f"Morpheus: Error in patreon_authorize: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/patreon/callback")
    async def patreon_callback(request):
        """Handle OAuth callback from Patreon and exchange code for token"""
        try:
            if not PATREON_CLIENT_ID or not PATREON_CLIENT_SECRET:
                return web.Response(
                    text="<html><body><h2>Error</h2><p>Patreon OAuth not configured</p></body></html>",
                    content_type="text/html"
                )
            
            code = request.query.get('code')
            error = request.query.get('error')
            received_state = request.query.get('state')
            
            if error:
                error_html = f"""
                <html>
                <head><title>Patreon Authorization Failed</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px; background: #1a1a2e; color: #eee;">
                    <h2 style="color: #ff6666;">Patreon Authorization Failed</h2>
                    <p>Error: {error}</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{type: 'patreon_oauth_complete', success: false, error: '{error}'}}, '*');
                        }}
                        setTimeout(function(){{window.close()}}, 3000);
                    </script>
                </body>
                </html>
                """
                return web.Response(text=error_html, content_type="text/html")
            
            state_file = os.path.join(NODE_DIR, ".patreon_oauth_state.json")
            if not os.path.exists(state_file):
                return web.Response(
                    text="<html><body><h2>Error</h2><p>OAuth state expired or invalid. Please try again.</p></body></html>",
                    content_type="text/html"
                )
            
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                os.remove(state_file)
                
                expires_at = datetime.fromisoformat(state_data.get('expires_at', '2000-01-01'))
                if datetime.now() > expires_at:
                    return web.Response(
                        text="<html><body><h2>Error</h2><p>OAuth state expired. Please try again.</p></body></html>",
                        content_type="text/html"
                    )
                
                stored_state = state_data.get('state', '')
                if not received_state or received_state != stored_state:
                    return web.Response(
                        text="<html><body><h2>Security Error</h2><p>Invalid state parameter. Possible CSRF attack detected.</p></body></html>",
                        content_type="text/html"
                    )
            except Exception as e:
                print(f"Morpheus: State validation error: {e}")
                return web.Response(
                    text="<html><body><h2>Error</h2><p>State validation failed. Please try again.</p></body></html>",
                    content_type="text/html"
                )
            
            if not code:
                return web.Response(
                    text="<html><body><h2>Error</h2><p>No authorization code received</p></body></html>",
                    content_type="text/html"
                )
            
            token_data = {
                "code": code,
                "grant_type": "authorization_code",
                "client_id": PATREON_CLIENT_ID,
                "client_secret": PATREON_CLIENT_SECRET,
                "redirect_uri": PATREON_REDIRECT_URI
            }
            
            encoded_data = urllib.parse.urlencode(token_data).encode('utf-8')
            token_request = urllib.request.Request(
                PATREON_TOKEN_URL,
                data=encoded_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            try:
                with urllib.request.urlopen(token_request, timeout=30) as response:
                    token_response = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                print(f"Morpheus: Token exchange error: {error_body}")
                return web.Response(
                    text=f"<html><body><h2>Token Exchange Failed</h2><p>{error_body}</p></body></html>",
                    content_type="text/html"
                )
            
            access_token = token_response.get('access_token')
            refresh_token = token_response.get('refresh_token')
            expires_in = token_response.get('expires_in', 2592000)
            
            if not access_token:
                return web.Response(
                    text="<html><body><h2>Error</h2><p>No access token received</p></body></html>",
                    content_type="text/html"
                )
            
            identity_url = f"{PATREON_API_URL}/identity?fields[user]=email,full_name"
            identity_request = urllib.request.Request(
                identity_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            try:
                with urllib.request.urlopen(identity_request, timeout=30) as response:
                    identity_data = json.loads(response.read().decode('utf-8'))
            except Exception as e:
                print(f"Morpheus: Identity fetch error: {e}")
                identity_data = {"data": {"attributes": {}}}
            
            user_email = identity_data.get('data', {}).get('attributes', {}).get('email', '')
            user_name = identity_data.get('data', {}).get('attributes', {}).get('full_name', '')
            user_id = identity_data.get('data', {}).get('id', '')
            
            patreon_auth = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat(),
                "user_email": user_email,
                "user_name": user_name,
                "user_id": user_id,
                "authenticated_at": datetime.now().isoformat()
            }
            
            try:
                with open(PATREON_AUTH_FILE, 'w', encoding='utf-8') as f:
                    json.dump(patreon_auth, f, indent=2)
            except Exception as e:
                print(f"Morpheus: Failed to save Patreon auth: {e}")
            
            success_html = f"""
            <html>
            <head>
                <title>Patreon Connected</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #1a1a2e; color: #eee; }}
                    .success {{ color: #4CAF50; font-size: 48px; }}
                    h2 {{ margin-top: 20px; }}
                    p {{ color: #aaa; }}
                </style>
            </head>
            <body>
                <div class="success">&#10004;</div>
                <h2>Patreon Connected Successfully!</h2>
                <p>Welcome, {user_name or user_email or 'Patron'}!</p>
                <p>You can close this window and return to ComfyUI.</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'patreon_oauth_complete', success: true}}, '*');
                    }}
                    setTimeout(function(){{window.close()}}, 2000);
                </script>
            </body>
            </html>
            """
            return web.Response(text=success_html, content_type="text/html")
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in patreon_callback: {traceback.format_exc()}")
            return web.Response(
                text=f"<html><body><h2>Error</h2><p>{str(e)}</p></body></html>",
                content_type="text/html"
            )

    @server.PromptServer.instance.routes.get("/morpheus/patreon/status")
    async def patreon_status(request):
        """Check current Patreon authentication status"""
        try:
            if not os.path.exists(PATREON_AUTH_FILE):
                return web.json_response({
                    "authenticated": False,
                    "message": "Not connected to Patreon"
                })
            
            with open(PATREON_AUTH_FILE, 'r', encoding='utf-8') as f:
                auth_data = json.load(f)
            
            expires_at = datetime.fromisoformat(auth_data.get('expires_at', '2000-01-01'))
            is_expired = datetime.now() > expires_at
            
            return web.json_response({
                "authenticated": True,
                "expired": is_expired,
                "user_email": auth_data.get('user_email', ''),
                "user_name": auth_data.get('user_name', ''),
                "authenticated_at": auth_data.get('authenticated_at', ''),
                "expires_at": auth_data.get('expires_at', '')
            })
        except Exception as e:
            return web.json_response({
                "authenticated": False,
                "error": str(e)
            })

    @server.PromptServer.instance.routes.post("/morpheus/patreon/logout")
    async def patreon_logout(request):
        """Clear Patreon authentication"""
        try:
            if os.path.exists(PATREON_AUTH_FILE):
                os.remove(PATREON_AUTH_FILE)
            return web.json_response({"status": "success", "message": "Logged out from Patreon"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/morpheus/patreon/check_membership")
    async def check_patreon_membership(request):
        """Check if the authenticated user is an active patron of the Morpheus campaign"""
        try:
            if not os.path.exists(PATREON_AUTH_FILE):
                return web.json_response({
                    "is_patron": False,
                    "error": "Not authenticated with Patreon"
                }, status=401)
            
            with open(PATREON_AUTH_FILE, 'r', encoding='utf-8') as f:
                auth_data = json.load(f)
            
            access_token = auth_data.get('access_token')
            if not access_token:
                return web.json_response({
                    "is_patron": False,
                    "error": "No access token available"
                }, status=401)
            
            def check_cached_membership_valid():
                """Check if cached membership is still valid for offline use (returns a COPY)"""
                cached_membership = auth_data.get('membership', {})
                if cached_membership.get('is_patron'):
                    membership_checked_at = auth_data.get('membership_checked_at', '')
                    if membership_checked_at:
                        try:
                            checked_dt = datetime.fromisoformat(membership_checked_at)
                            if datetime.now() - checked_dt < timedelta(days=7):
                                return dict(cached_membership)
                        except:
                            pass
                return None
            
            expires_at = datetime.fromisoformat(auth_data.get('expires_at', '2000-01-01'))
            if datetime.now() > expires_at:
                refresh_result = await refresh_patreon_token(auth_data)
                if not refresh_result.get('success'):
                    # Token expired and refresh failed - return needs_reauth 
                    # but also check for cached membership for graceful offline handling
                    cached = check_cached_membership_valid()
                    if cached:
                        # Return cached data but flag that reauth is needed
                        cached['cached'] = True
                        cached['offline_mode'] = True
                        cached['token_expired'] = True
                        cached['needs_reauth'] = True
                        return web.json_response(cached)
                    return web.json_response({
                        "is_patron": False,
                        "error": "Token expired and refresh failed - please reconnect with Patreon",
                        "needs_reauth": True
                    }, status=401)
                access_token = refresh_result.get('access_token')
            
            identity_url = (
                f"{PATREON_API_URL}/identity?"
                "include=memberships,memberships.campaign,memberships.currently_entitled_tiers&"
                "fields[member]=patron_status,last_charge_status,currently_entitled_amount_cents,lifetime_support_cents&"
                "fields[user]=email,full_name"
            )
            
            identity_request = urllib.request.Request(
                identity_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "Morpheus-ComfyUI-Node"
                }
            )
            
            try:
                with urllib.request.urlopen(identity_request, timeout=30) as response:
                    identity_data = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                print(f"Morpheus: Patreon identity error: {error_body}")
                return web.json_response({
                    "is_patron": False,
                    "error": f"Failed to fetch Patreon identity: {e.code}"
                }, status=500)
            except urllib.error.URLError as e:
                print(f"Morpheus: Network error checking Patreon: {e}")
                cached = check_cached_membership_valid()
                if cached:
                    cached['cached'] = True
                    cached['offline_mode'] = True
                    return web.json_response(cached)
                return web.json_response({
                    "is_patron": False,
                    "error": "Network unavailable and no valid cached membership",
                    "offline": True
                }, status=503)
            
            from .config import PATREON_CAMPAIGN_ID
            
            included = identity_data.get('included', [])
            is_active_patron = False
            patron_tier = None
            patron_status = None
            campaign_id = None
            
            for resource in included:
                if resource.get('type') == 'member':
                    member_campaign = resource.get('relationships', {}).get('campaign', {}).get('data', {})
                    member_campaign_id = member_campaign.get('id', '')
                    
                    if PATREON_CAMPAIGN_ID and member_campaign_id != PATREON_CAMPAIGN_ID:
                        continue
                    
                    attributes = resource.get('attributes', {})
                    patron_status = attributes.get('patron_status', '')
                    last_charge_status = attributes.get('last_charge_status', '')
                    
                    if patron_status == 'active_patron':
                        is_active_patron = True
                        campaign_id = member_campaign_id
                        
                        entitled_tiers = resource.get('relationships', {}).get('currently_entitled_tiers', {}).get('data', [])
                        if entitled_tiers:
                            patron_tier = entitled_tiers[0].get('id')
                        break
            
            membership_data = {
                "is_patron": is_active_patron,
                "patron_status": patron_status,
                "campaign_id": campaign_id,
                "tier_id": patron_tier,
                "user_email": auth_data.get('user_email', ''),
                "user_name": auth_data.get('user_name', ''),
                "checked_at": datetime.now().isoformat()
            }
            
            auth_data['membership'] = membership_data
            auth_data['membership_checked_at'] = datetime.now().isoformat()
            try:
                with open(PATREON_AUTH_FILE, 'w', encoding='utf-8') as f:
                    json.dump(auth_data, f, indent=2)
            except Exception as e:
                print(f"Morpheus: Failed to cache membership: {e}")
            
            return web.json_response(membership_data)
            
        except Exception as e:
            import traceback
            print(f"Morpheus: Error in check_patreon_membership: {traceback.format_exc()}")
            return web.json_response({
                "is_patron": False,
                "error": str(e)
            }, status=500)

    async def refresh_patreon_token(auth_data: dict) -> dict:
        """Refresh an expired Patreon access token using the refresh token"""
        try:
            refresh_token = auth_data.get('refresh_token')
            if not refresh_token:
                return {"success": False, "error": "No refresh token available"}
            
            if not PATREON_CLIENT_ID or not PATREON_CLIENT_SECRET:
                return {"success": False, "error": "Patreon OAuth not configured"}
            
            token_data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": PATREON_CLIENT_ID,
                "client_secret": PATREON_CLIENT_SECRET
            }
            
            encoded_data = urllib.parse.urlencode(token_data).encode('utf-8')
            token_request = urllib.request.Request(
                PATREON_TOKEN_URL,
                data=encoded_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            with urllib.request.urlopen(token_request, timeout=30) as response:
                token_response = json.loads(response.read().decode('utf-8'))
            
            new_access_token = token_response.get('access_token')
            new_refresh_token = token_response.get('refresh_token', refresh_token)
            expires_in = token_response.get('expires_in', 2592000)
            
            if not new_access_token:
                return {"success": False, "error": "No access token in refresh response"}
            
            auth_data['access_token'] = new_access_token
            auth_data['refresh_token'] = new_refresh_token
            auth_data['expires_at'] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            auth_data['refreshed_at'] = datetime.now().isoformat()
            
            try:
                with open(PATREON_AUTH_FILE, 'w', encoding='utf-8') as f:
                    json.dump(auth_data, f, indent=2)
            except Exception as e:
                print(f"Morpheus: Failed to save refreshed token: {e}")
            
            return {"success": True, "access_token": new_access_token}
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"Morpheus: Token refresh error: {error_body}")
            return {"success": False, "error": f"Token refresh failed: {e.code}"}
        except Exception as e:
            print(f"Morpheus: Token refresh exception: {e}")
            return {"success": False, "error": str(e)}

# Register routes when ComfyUI is available
if COMFYUI_AVAILABLE and server:
    try:
        register_routes()
    except Exception as e:
        print(f"Morpheus: Failed to register routes: {e}")

class MorpheusModelManagement:
    """ComfyUI custom node for talent model management and selection"""
    
    def __init__(self):
        self.catalog_manager = None
        self.node_id = str(uuid.uuid4())
        self.last_selected_talent = None
        
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "selected_talent_id": ("STRING", {"default": "", "multiline": False, "forceInput": True}),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "description", "metadata")
    FUNCTION = "select_talent"
    CATEGORY = "Morpheus/Talent"
    
    def select_talent(
        self,
        unique_id=None,
        extra_pnginfo=None,
        selected_talent_id: str = ""
    ) -> Tuple[torch.Tensor, str, str]:
        """Main function called by ComfyUI to select and return talent data"""
        
        # Use fixed paths for local catalog (fallback)
        catalog_path = "catalog/catalog.json"
        images_folder = "catalog/images" 
        thumbnail_size = 150
        
        # Resolve paths relative to node directory
        full_catalog_path = os.path.join(NODE_DIR, catalog_path)
        full_images_path = os.path.join(NODE_DIR, images_folder)
        
        # Initialize catalog manager for local fallback
        if not self.catalog_manager:
            self.catalog_manager = CatalogManager(full_catalog_path)
        
        # Try to load from REMOTE catalog first (Patreon patrons get remote access)
        catalog_data = None
        using_remote = False
        
        remote_catalog = fetch_remote_catalog()
        if remote_catalog and remote_catalog.get("talents"):
            catalog_data = remote_catalog
            using_remote = True
            # Add remote image URLs to talents
            add_remote_image_urls(catalog_data.get("talents", []))
            print(f"Morpheus: Using remote catalog with {len(catalog_data.get('talents', []))} talents")
        else:
            # Fallback to local catalog
            catalog_data = self.catalog_manager.load_catalog()
            if not catalog_data.get("talents"):
                # Create sample catalog if empty
                catalog_data = create_sample_catalog()
                try:
                    self.catalog_manager.save_catalog(catalog_data)
                except:
                    pass
            print(f"Morpheus: Using local catalog with {len(catalog_data.get('talents', []))} talents")
        
        # Generate thumbnails if needed (only for local catalog)
        if not using_remote and not self._thumbnails_exist(os.path.dirname(full_catalog_path)):
            self._generate_thumbnails(catalog_data, os.path.dirname(full_catalog_path), thumbnail_size)
        
        # Select talent
        selected_talent = None
        if selected_talent_id:
            selected_talent = next((t for t in catalog_data.get("talents", []) if t["id"] == selected_talent_id), None)
        
        if not selected_talent and catalog_data.get("talents"):
            # Default to first talent if none selected
            selected_talent = catalog_data["talents"][0]
        
        if not selected_talent:
            # Return placeholder if no talent found
            return self._create_placeholder_output()
        
        # Load image
        image_tensor = self._load_talent_image(selected_talent, os.path.dirname(full_catalog_path))
        
        # Generate description
        if not selected_talent.get("description"):
            selected_talent["description"] = self.catalog_manager.generate_description(selected_talent)
        
        # Extract description
        description = selected_talent.get("description", "No description available")
        
        # Format metadata for display
        metadata_lines = []
        metadata_lines.append(f"Name: {selected_talent.get('name', 'Unknown')}")
        metadata_lines.append(f"ID: {selected_talent.get('id', 'N/A')}")
        if selected_talent.get('gender'):
            metadata_lines.append(f"Gender: {selected_talent['gender']}")
        if selected_talent.get('age_group'):
            metadata_lines.append(f"Age Group: {selected_talent['age_group']}")
        if selected_talent.get('ethnicity'):
            metadata_lines.append(f"Ethnicity: {selected_talent['ethnicity']}")
        if selected_talent.get('tags'):
            metadata_lines.append(f"Tags: {', '.join(selected_talent['tags'])}")
        if selected_talent.get('is_favorite'):
            metadata_lines.append(f"Favorite: {selected_talent['is_favorite']}")
        
        metadata_text = "\n".join(metadata_lines)
        
        self.last_selected_talent = selected_talent
        
        return (image_tensor, description, metadata_text)
    
    def _scan_folder_and_generate_catalog(self, images_folder: str, catalog_path: str) -> Dict[str, Any]:
        """Scan images folder and generate automatic catalog"""
        catalog_data = {
            "version": "1.0",
            "description": "Auto-generated Morpheus Model Management Catalog",
            "talents": []
        }
        
        if not os.path.exists(images_folder):
            os.makedirs(images_folder, exist_ok=True)
            return catalog_data
        
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        
        for filename in os.listdir(images_folder):
            name, ext = os.path.splitext(filename)
            if ext.lower() in supported_extensions:
                talent_id = f"talent_{name.lower().replace(' ', '_').replace('-', '_')}"
                
                talent_entry = {
                    "id": talent_id,
                    "name": name.replace('_', ' ').replace('-', ' ').title(),
                    "image_path": f"images/{filename}",
                    "description": f"Auto-generated entry for {name}",
                    "tags": ["auto_generated"],
                    "copyright": "Unknown"
                }
                
                catalog_data["talents"].append(talent_entry)
        
        # Save auto-generated catalog
        try:
            if self.catalog_manager:
                self.catalog_manager.save_catalog(catalog_data)
        except Exception as e:
            print(f"Could not save auto-generated catalog: {e}")
        
        return catalog_data
    
    def _thumbnails_exist(self, base_path: str) -> bool:
        """Check if thumbnail directory exists with some thumbnails"""
        thumb_dir = os.path.join(base_path, ".thumbnails")
        if not os.path.exists(thumb_dir):
            return False
        return len(os.listdir(thumb_dir)) > 0
    
    def _generate_thumbnails(self, catalog_data: Dict[str, Any], base_path: str, size: int):
        """Generate thumbnail images for all talents"""
        thumb_dir = os.path.join(base_path, ".thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        
        for talent in catalog_data.get("talents", []):
            image_path = os.path.join(base_path, talent["image_path"])
            thumb_path = os.path.join(thumb_dir, f"{talent['id']}_thumb.jpg")
            
            if os.path.exists(image_path) and not os.path.exists(thumb_path):
                try:
                    with Image.open(image_path) as img:
                        # Convert to RGB if necessary
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        
                        # Create thumbnail
                        img.thumbnail((size, size), Image.Resampling.LANCZOS)
                        img.save(thumb_path, "JPEG", quality=85)
                        
                except Exception as e:
                    print(f"Could not generate thumbnail for {talent['id']}: {e}")
    
    def _load_talent_image(self, talent: Dict[str, Any], base_path: str) -> torch.Tensor:
        """Load talent image and convert to tensor - supports both local and remote cached images"""
        talent_id = talent.get('id', '')
        talent_image_path = talent.get("image_path", "")
        
        # First check if image is in remote cache
        if talent_id:
            cached_tensor = load_cached_image_as_tensor(talent_id)
            if cached_tensor is not None:
                return cached_tensor
        
        # Check for remote URL in image_path
        if talent_image_path.startswith('http'):
            # Try to download and cache synchronously
            cache_path = get_cached_image_path(talent_id)
            if not os.path.exists(cache_path):
                try:
                    with urllib.request.urlopen(talent_image_path, timeout=30) as response:
                        content = response.read()
                        ensure_cache_dir()
                        with open(cache_path, 'wb') as f:
                            f.write(content)
                        print(f"Morpheus: Downloaded and cached image for {talent_id}")
                except Exception as e:
                    print(f"Morpheus: Failed to download remote image for {talent_id}: {e}")
            
            # Try to load from cache
            cached_tensor = load_cached_image_as_tensor(talent_id)
            if cached_tensor is not None:
                return cached_tensor
        
        # Fall back to local file path
        image_path = os.path.join(base_path, talent_image_path)
        
        if not os.path.exists(image_path):
            return self._create_placeholder_image()
        
        try:
            with Image.open(image_path) as img:
                # Convert to RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Convert to numpy array
                img_array = np.array(img).astype(np.float32) / 255.0
                
                # Convert to tensor with batch dimension [1, H, W, C]
                img_tensor = torch.from_numpy(img_array).unsqueeze(0)
                
                return img_tensor
                
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            return self._create_placeholder_image()
    
    def _create_placeholder_image(self) -> torch.Tensor:
        """Create a placeholder image tensor"""
        # Create a 512x512 gray placeholder
        placeholder = np.full((512, 512, 3), 0.5, dtype=np.float32)
        return torch.from_numpy(placeholder).unsqueeze(0)
    
    def _create_placeholder_output(self) -> Tuple[torch.Tensor, str, str]:
        """Create placeholder output when no talent is selected"""
        image_tensor = self._create_placeholder_image()
        description = "No talent selected"
        metadata = "No metadata available"
        return (image_tensor, description, metadata)
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Return hash for caching - node should re-execute when inputs change"""
        # Create hash from relevant inputs
        relevant_inputs = [
            kwargs.get("selected_talent_id", ""),
            kwargs.get("refresh_thumbnails", False)
        ]
        return hash(str(relevant_inputs))

NODE_CLASS_MAPPINGS = {
    "MorpheusModelManagement": MorpheusModelManagement
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MorpheusModelManagement": "Morpheus Model Management"
}