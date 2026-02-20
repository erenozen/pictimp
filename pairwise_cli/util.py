"""Utility functions for pairwise-cli."""
import os
import re

def make_safe_name(display_name: str, existing_names: set) -> str:
    """
    Converts a display name (with spaces/symbols) to an alphanumeric safe name.
    Ensures uniqueness against `existing_names`.
    """
    safe = re.sub(r'\s+', '_', display_name)
    safe = re.sub(r'[^A-Za-z0-9_]', '', safe)
    if not safe:
        safe = "P"
    
    base_safe = safe
    idx = 2
    while safe in existing_names:
        safe = f"{base_safe}_{idx}"
        idx += 1
        
    return safe
