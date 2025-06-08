import json
import os
from typing import Any, Dict, Optional

from backend.app_recipe.consts import MOCK_FOLDER


def save_mock_data(route_name: str, data: Dict[str, Any]) -> None:
    """
    Save mock data to a JSON file if it doesn't exist or is empty
    
    Args:
        route_name: Name of the route (will be used as filename)
        data: The data to save
    """
    # Create mock_data directory if it doesn't exist
    mock_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_data")
    os.makedirs(mock_dir, exist_ok=True)

    # Create filename
    filename = f"{route_name}_response.json"
    filepath = os.path.join(mock_dir, filename)

    # Check if file exists and is not empty
    should_save = True
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                existing_data = json.load(f)
                if existing_data:  # If file has data, don't overwrite
                    should_save = False
        except json.JSONDecodeError:
            # If file is corrupted, we'll overwrite it
            pass

    if should_save:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


def load_mock_data(route_name: str) -> Optional[Dict[str, Any]]:
    """
    Load mock data from a JSON file
    
    Args:
        route_name: Name of the route (will be used as filename)
    
    Returns:
        The loaded data or None if file doesn't exist or is empty
    """
    # Save response to JSON file in mock folder only if it doesn't exist
    os.makedirs(MOCK_FOLDER, exist_ok=True)
    filepath = os.path.join(MOCK_FOLDER, f"{route_name}.json")

    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return data if data else None
    except json.JSONDecodeError:
        return None
