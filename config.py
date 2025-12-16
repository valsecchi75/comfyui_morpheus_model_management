"""
Morpheus Model Management - Configuration
Remote catalog and Patreon authentication settings
"""
import os

# Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hrlwqnqqgcxxezagyfah.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhybHdxbnFxZ2N4eGV6YWd5ZmFoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzQxNDAyNjEsImV4cCI6MjA0OTcxNjI2MX0.jCvvk6Dk1m2qrkXzDZvYiO-QHRE9cPz9MOl_Bwifnw0")

# Supabase Edge Functions URL (for Patreon OAuth)
SUPABASE_FUNCTIONS_URL = f"{SUPABASE_URL}/functions/v1"

# Remote Catalog URLs
CATALOG_BASE_URL = f"{SUPABASE_URL}/storage/v1/object/public/morpheus-catalog"
CATALOG_JSON_URL = f"{CATALOG_BASE_URL}/catalog.json"
IMAGES_BASE_URL = f"{CATALOG_BASE_URL}/images"
THUMBNAILS_BASE_URL = f"{CATALOG_BASE_URL}/thumbnails"

# License Validation Settings (deprecated - now using Patreon OAuth via Supabase)
LICENSE_CACHE_DAYS = 7
LICENSE_OFFLINE_GRACE_DAYS = 7

# Patreon OAuth Configuration (deprecated - now handled by Supabase Edge Functions)
PATREON_CLIENT_ID = os.environ.get("PATREON_CLIENT_ID", "")
PATREON_CLIENT_SECRET = os.environ.get("PATREON_CLIENT_SECRET", "")
PATREON_CREATOR_ACCESS_TOKEN = os.environ.get("PATREON_CREATOR_ACCESS_TOKEN", "")
PATREON_REDIRECT_URI = "http://127.0.0.1:8188/morpheus/patreon/callback"
PATREON_AUTHORIZE_URL = "https://www.patreon.com/oauth2/authorize"
PATREON_TOKEN_URL = "https://www.patreon.com/api/oauth2/token"
PATREON_API_URL = "https://www.patreon.com/api/oauth2/v2"
