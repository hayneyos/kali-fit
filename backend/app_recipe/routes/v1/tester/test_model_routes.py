import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import os
import requests
import json
from pathlib import Path
import io
from PIL import Image
import shutil

from backend.app_recipe.routes.v1.prod.model_routes import router as prod_router
from backend.app_recipe.routes.v1.mock.mock_model_routes import router as mock_router
from backend.app_recipe.consts import UPLOAD_FOLDER_APP, RECIPE_FOLDER_APP

# Base URLs for the APIs
PROD_BASE_URL = "https://for-checking.live/api/"  # Update this with your actual production URL
MOCK_BASE_URL = "https://for-checking.live/api/mock"  # Update this with your actual mock URL

# Test data
TEST_IMAGE_PATH = "resource/BANANA.jpg"
TEST_IMAGE_CONTENT = b"fake image content"

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test"""
    # Create resource directory if it doesn't exist
    os.makedirs("resource", exist_ok=True)
    
    # Create test image in resource directory
    with open(TEST_IMAGE_PATH, "wb") as f:
        f.write(TEST_IMAGE_CONTENT)
    
    # Create upload directories
    os.makedirs(UPLOAD_FOLDER_APP, exist_ok=True)
    os.makedirs(RECIPE_FOLDER_APP, exist_ok=True)
    
    yield
    
    # Cleanup
    if os.path.exists(TEST_IMAGE_PATH):
        os.remove(TEST_IMAGE_PATH)
    
    # Clean mock data directory
    mock_data_dir = Path(__file__).parent.parent / "mock_data"
    if mock_data_dir.exists():
        for file in mock_data_dir.glob("*.json"):
            file.unlink()

def test_find_ingredient_by_image():
    """Test finding ingredients by image"""
    # Read the existing mock image file
    mock_file_path = os.path.join("/home/data/kaila/", 'mock', 'BANANA.jpg')
    if not os.path.exists(mock_file_path):
        raise FileNotFoundError(f"Mock image not found at: {mock_file_path}")
    
    with open(mock_file_path, 'rb') as f:
        img_byte_arr = io.BytesIO(f.read())
        img_byte_arr.seek(0)

    # Test case 1: Valid image upload
    files = {
        'file': ('BANANA.jpg', img_byte_arr, 'image/jpeg')
    }
    response = requests.post(f"{PROD_BASE_URL}/find_ingredient_by_image", files=files)
    print("\nImage Analysis Response:")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "ingredients" in data
    assert "total_items" in data
    assert "refrigerator_status" in data
    assert "recommendations" in data
    assert isinstance(data["ingredients"], list)
    assert isinstance(data["recommendations"], list)

def test_find_ingredient_by_image_invalid_file_type():
    """Test finding ingredients with invalid file type"""
    # Create a text file in memory
    text_content = b"This is not an image"
    text_file = io.BytesIO(text_content)

    # Test case: Invalid file type
    files = {
        'file': ('test.txt', text_file, 'text/plain')
    }
    response = requests.post(f"{PROD_BASE_URL}/find_ingredient_by_image", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "File must be an image" in data["error"]

def test_find_ingredient_by_image_no_file():
    """Test finding ingredients without file"""
    response = requests.post(f"{PROD_BASE_URL}/find_ingredient_by_image")
    assert response.status_code == 422  # FastAPI validation error

def test_find_ingredient_by_image_empty_file():
    """Test finding ingredients with empty file"""
    empty_file = io.BytesIO(b"")
    files = {
        'file': ('empty.jpg', empty_file, 'image/jpeg')
    }
    response = requests.post(f"{PROD_BASE_URL}/find_ingredient_by_image", files=files)
    assert response.status_code == 500  # Server error for empty file

def test_predict_meals_mock():
    """Test the mock OpenAI proxy endpoint"""
    # Test case: Basic request to mock endpoint
    response = requests.post(
        f"{MOCK_BASE_URL}/predict_meals",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Test message"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"https://for-checking.live/api/uploads/image_picker_DAC7BBC1-87B9-49B4-8348-610606087954-1936-00000036C74D79E6.jpg",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            "model": "google/gemini-2.5-flash-preview",
            "email": "test@example.com",
            "device_id": "test-device-123",
            "image_name": TEST_IMAGE_PATH,
            "version": "v1"
        }
    )
    
    # Print the response for debugging
    print("\nMock Response:")
    print(json.dumps(response.json(), indent=2))
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
#
# def test_predict_meals_prod():
#     """Test the production OpenAI proxy endpoint"""
#     # Test case 1: Basic request
#     response = requests.post(
#         f"{PROD_BASE_URL}/predict_meals",
#         json={
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": [
#                         {
#                             "type": "text",
#                             "text": "Test message"
#                         },
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"https://for-checking.live/api/uploads/image_picker_DAC7BBC1-87B9-49B4-8348-610606087954-1936-00000036C74D79E6.jpg",
#                                 "detail": "high"
#                             }
#                         }
#                     ]
#                 }
#             ],
#             "model": "google/gemini-2.5-flash-preview",
#             "email": "test@example.com",
#             "device_id": "test-device-123",
#             "image_name": TEST_IMAGE_PATH,
#             "version": "v1"
#         }
#     )
#
#     # Print the response for debugging
#     print("\nProduction Response:")
#     print(json.dumps(response.json(), indent=2))
#
#     assert response.status_code == 200
#     data = response.json()
#     assert "choices" in data
#     assert len(data["choices"]) > 0
#
