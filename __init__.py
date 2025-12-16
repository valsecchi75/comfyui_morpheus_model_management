"""
ComfyUI Morpheus Model Management - Talent Browser Node
Custom node for browsing and selecting talent models with metadata
"""

from .morpheus_model_management import MorpheusModelManagement

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "MorpheusModelManagement": MorpheusModelManagement
}

# Display names for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
    "MorpheusModelManagement": "Morpheus Model Management"
}

# JavaScript extension directory for ComfyUI native gallery
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']