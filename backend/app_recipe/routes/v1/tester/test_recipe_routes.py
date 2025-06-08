import pytest
import requests
import os
import json
from pathlib import Path

# Base URL for the API
PROD_BASE_URL = "https://for-checking.live/api/"  # Update this with your actual production URL

# Test data
TEST_IMAGE_PATH = "test_image.jpg"
TEST_IMAGE_CONTENT = b"fake image content"


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test"""
    # Create test image
    with open(TEST_IMAGE_PATH, "wb") as f:
        f.write(TEST_IMAGE_CONTENT)

    yield

    # Cleanup
    if os.path.exists(TEST_IMAGE_PATH):
        os.remove(TEST_IMAGE_PATH)

    # Clean mock data directory
    mock_data_dir = Path(__file__).parent.parent / "mock_data"
    if mock_data_dir.exists():
        for file in mock_data_dir.glob("*.json"):
            file.unlink()


def test_get_recipe():
    """Test the get recipe endpoint"""
    response = requests.get(
        f"{PROD_BASE_URL}get_recipe",
        params={
            "ingredients": "chicken,rice",
            "diet_type": "balanced",
            "meal_type": "lunch"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "recipes" in data
    assert len(data["recipes"]) > 0


def test_get_recipe_missing_params():
    """Test get recipe with missing parameters"""
    response = requests.get(f"{PROD_BASE_URL}get_recipe")
    assert response.status_code == 422  # Validation error


def test_find_ingredient_empty_query():
    """Test find ingredient with empty query"""
    response = requests.get(
        f"{PROD_BASE_URL}find_ingredient",
        params={"query": ""}
    )
    assert response.status_code == 422  # Validation error
