"""
Schema definitions for the Morpheus Model Management catalog
"""

import json
import os
from typing import Dict, List, Any, Optional

# Schema for talent entry in catalog.json
TALENT_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "image_path"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-zA-Z0-9_]+$"},
        "name": {"type": "string", "minLength": 1},
        "gender": {"type": "string", "enum": ["male", "female", "non_binary", "other"]},
        "age_group": {"type": "string", "enum": ["child", "teen", "young_adult", "adult", "mature", "senior"]},
        "ethnicity": {"type": "string", "enum": ["caucasian", "african", "asian", "hispanic", "mixed", "middle_eastern", "other"]},
        "skin_tone": {"type": "string", "enum": ["very_light", "light", "light_warm", "medium", "medium_warm", "dark", "very_dark"]},
        "hair_color": {"type": "string", "enum": ["blonde", "brown", "black", "red", "auburn", "brown_auburn", "gray", "white", "other"]},
        "hair_style": {"type": "string", "enum": ["short", "medium", "long", "curly", "wavy", "straight", "long_wavy", "bald", "other"]},
        "eye_color": {"type": "string", "enum": ["blue", "brown", "green", "hazel", "gray", "amber", "other"]},
        "body_type": {"type": "string", "enum": ["slim", "athletic", "average", "curvy", "plus_size", "slim_tall", "other"]},
        "freckles": {"type": "boolean"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "image_path": {"type": "string"},
        "copyright": {"type": "string"},
        "download_url": {"type": "string"},
        "is_favorite": {"type": "boolean"}
    }
}

class CatalogManager:
    """Manager for handling catalog operations"""
    
    def __init__(self, catalog_path: str):
        self.catalog_path = catalog_path
        self.catalog_data = None
        
    def load_catalog(self) -> Dict[str, Any]:
        """Load catalog from JSON file"""
        if os.path.exists(self.catalog_path):
            try:
                with open(self.catalog_path, 'r', encoding='utf-8') as f:
                    self.catalog_data = json.load(f)
                return self.catalog_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading catalog: {e}")
                return {"talents": []}
        return {"talents": []}
    
    def save_catalog(self, catalog_data: Dict[str, Any]) -> bool:
        """Save catalog to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            with open(self.catalog_path, 'w', encoding='utf-8') as f:
                json.dump(catalog_data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving catalog: {e}")
            return False
    
    def generate_description(self, talent: Dict[str, Any]) -> str:
        """Generate description from talent metadata"""
        parts = []
        
        # Age and gender
        if talent.get('age_group') and talent.get('gender'):
            parts.append(f"{talent['age_group'].replace('_', ' ')} {talent['gender']}")
        
        # Physical characteristics
        if talent.get('hair_color') and talent.get('hair_style'):
            hair_desc = f"{talent['hair_style'].replace('_', ' ')} {talent['hair_color'].replace('_', ' ')} hair"
            parts.append(hair_desc)
        
        if talent.get('skin_tone'):
            parts.append(f"{talent['skin_tone'].replace('_', ' ')} skin")
        
        if talent.get('eye_color'):
            parts.append(f"{talent['eye_color']} eyes")
        
        # Special features
        if talent.get('freckles'):
            parts.append("with freckles")
        
        # Tags
        if talent.get('tags'):
            tag_style = ", ".join(talent['tags'][:2])  # First 2 tags
            parts.append(f"{tag_style} style")
        
        if parts:
            return "; ".join(parts) + "."
        else:
            return talent.get('description', f"Talent: {talent.get('name', 'Unknown')}")
    
    def filter_talents(self, talents: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Filter talents based on criteria"""
        filtered = talents
        
        # Name filter
        if filters.get('name_filter'):
            name_filter = filters['name_filter'].lower()
            filtered = [t for t in filtered if name_filter in t.get('name', '').lower()]
        
        # Tag filters
        if filters.get('tag_filter'):
            tag_filters = filters['tag_filter']
            if isinstance(tag_filters, str):
                tag_filters = [tag_filters]
            
            if filters.get('tag_logic') == 'AND':
                # All tags must be present
                filtered = [t for t in filtered if all(tag in t.get('tags', []) for tag in tag_filters)]
            else:
                # Any tag must be present (OR logic)
                filtered = [t for t in filtered if any(tag in t.get('tags', []) for tag in tag_filters)]
        
        # Attribute filters
        for attr in ['gender', 'age_group', 'ethnicity', 'skin_tone', 'hair_color', 'hair_style', 'eye_color', 'body_type']:
            if filters.get(attr):
                filtered = [t for t in filtered if t.get(attr) == filters[attr]]
        
        # Favorites filter
        if filters.get('favorites_only'):
            filtered = [t for t in filtered if t.get('is_favorite', False)]
        
        return filtered

def create_sample_catalog() -> Dict[str, Any]:
    """Create a sample catalog with example talent entries"""
    return {
        "version": "1.0",
        "description": "Morpheus Model Management Talent Catalog",
        "talents": [
            {
                "id": "talent_lia_001",
                "name": "Lia",
                "gender": "female",
                "age_group": "young_adult",
                "ethnicity": "mixed",
                "skin_tone": "light_warm",
                "hair_color": "brown_auburn",
                "hair_style": "long_wavy",
                "eye_color": "green",
                "body_type": "slim_tall",
                "freckles": True,
                "tags": ["editorial", "sporty"],
                "description": "Young adult with soft waves and light freckles, editorial look.",
                "image_path": "images/lia_001.jpg",
                "copyright": "Morpheus Model Management",
                "download_url": ""
            },
            {
                "id": "talent_marco_002",
                "name": "Marco",
                "gender": "male",
                "age_group": "adult",
                "ethnicity": "caucasian",
                "skin_tone": "medium",
                "hair_color": "brown",
                "hair_style": "short",
                "eye_color": "blue",
                "body_type": "athletic",
                "freckles": False,
                "tags": ["fashion", "commercial"],
                "description": "Professional adult male model with athletic build.",
                "image_path": "images/marco_002.jpg",
                "copyright": "Morpheus Model Management",
                "download_url": ""
            },
            {
                "id": "talent_sofia_003",
                "name": "Sofia",
                "gender": "female",
                "age_group": "teen",
                "ethnicity": "hispanic",
                "skin_tone": "medium_warm",
                "hair_color": "black",
                "hair_style": "long",
                "eye_color": "brown",
                "body_type": "slim",
                "freckles": False,
                "tags": ["lifestyle", "beauty"],
                "description": "Teen model with natural beauty and lifestyle appeal.",
                "image_path": "images/sofia_003.jpg",
                "copyright": "Morpheus Model Management",
                "download_url": ""
            }
        ]
    }