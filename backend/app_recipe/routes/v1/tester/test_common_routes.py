import os
import pytest
import requests
from backend.app_recipe.consts import RECIPE_FOLDER_APP, UPLOAD_FOLDER_APP
import io
from PIL import Image
import json

# Base URL for the API

BASE_URL = "https://for-checking.live/api/"  # Update this with your actual production URL

# Test data
TEST_FILENAME = "BANANA.jpg"
TEST_CONTENT = b"Hello, this is a test file content"

@pytest.fixture(autouse=True)
def setup_and_cleanup():
    # Create test directories if they don't exist
    os.makedirs(RECIPE_FOLDER_APP, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER_APP, exist_ok=True)
    
    yield
    
    # Cleanup test files after tests
    test_files = [
        os.path.join(RECIPE_FOLDER_APP, TEST_FILENAME),
        os.path.join(UPLOAD_FOLDER_APP, TEST_FILENAME)
    ]
    for file_path in test_files:
        if os.path.exists(file_path):
            os.remove(file_path)

def test_upload_file_to_recipe_folder():
    # Test uploading file to recipe folder
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain'),
        'directory': (None, RECIPE_FOLDER_APP)
    }
    
    response = requests.post(f"{BASE_URL}/upload", files=files)
    assert response.status_code == 200
    assert response.json() == {"filename": TEST_FILENAME}
    
    # Verify file exists in recipe folder
    file_path = os.path.join(RECIPE_FOLDER_APP, TEST_FILENAME)
    assert os.path.exists(file_path)
    with open(file_path, 'rb') as f:
        assert f.read() == TEST_CONTENT

def test_upload_file_to_upload_folder():
    # Test uploading file to upload folder
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain'),
        'directory': (None, UPLOAD_FOLDER_APP)
    }
    
    response = requests.post(f"{BASE_URL}/upload", files=files)
    assert response.status_code == 200
    assert response.json() == {"filename": TEST_FILENAME}
    
    # Verify file exists in upload folder
    file_path = os.path.join(UPLOAD_FOLDER_APP, TEST_FILENAME)
    assert os.path.exists(file_path)
    with open(file_path, 'rb') as f:
        assert f.read() == TEST_CONTENT

def test_get_file_from_recipe_folder():
    # First upload a file to recipe folder
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain'),
        'directory': (None, RECIPE_FOLDER_APP)
    }
    requests.post(f"{BASE_URL}/upload", files=files)
    
    # Test retrieving the file
    response = requests.get(f"{BASE_URL}/uploads/{TEST_FILENAME}/recipe")
    assert response.status_code == 200
    assert response.content == TEST_CONTENT

def test_get_file_from_upload_folder():
    # First upload a file to upload folder
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain'),
        'directory': (None, UPLOAD_FOLDER_APP)
    }
    requests.post(f"{BASE_URL}/upload", files=files)
    
    # Test retrieving the file
    response = requests.get(f"{BASE_URL}/uploads/{TEST_FILENAME}/recipe")
    assert response.status_code == 200
    assert response.content == TEST_CONTENT

def test_get_nonexistent_file():
    # Test getting a file that doesn't exist
    response = requests.get(f"{BASE_URL}/uploads/nonexistent.txt/recipe")
    assert response.status_code == 404

def test_upload_file_without_directory():
    # Test uploading file without directory parameter
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain')
    }
    
    response = requests.post(f"{BASE_URL}/upload", files=files)
    assert response.status_code == 200
    assert response.json() == {"filename": TEST_FILENAME}
    
    # Verify file exists in upload folder (default)
    file_path = os.path.join(UPLOAD_FOLDER_APP, TEST_FILENAME)
    assert os.path.exists(file_path)
    with open(file_path, 'rb') as f:
        assert f.read() == TEST_CONTENT

def test_get_file_with_empty_directory():
    # First upload a file to upload folder
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain'),
        'directory': (None, UPLOAD_FOLDER_APP)
    }
    requests.post(f"{BASE_URL}/upload", files=files)
    
    # Test retrieving the file without specifying directory
    response = requests.get(f"{BASE_URL}/uploads/{TEST_FILENAME}")
    assert response.status_code == 200
    assert response.content == TEST_CONTENT

def test_upload_file_without_directory_specified():
    # Test uploading file without directory parameter
    files = {
        'file': (TEST_FILENAME, TEST_CONTENT, 'text/plain')
    }
    
    response = requests.post(f"{BASE_URL}/upload", files=files)
    assert response.status_code == 200
    assert response.json() == {"filename": TEST_FILENAME}
    
    # Verify file exists in upload folder (default)
    file_path = os.path.join(UPLOAD_FOLDER_APP, TEST_FILENAME)
    assert os.path.exists(file_path)
    with open(file_path, 'rb') as f:
        assert f.read() == TEST_CONTENT

def test_find_ingredient_by_name():
    """Test finding ingredients by name"""
    # Test case 1: Basic search in English
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "apple", "lang": "en"})
    print("\nEnglish Search Response:")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert all("primary_name" in item for item in data["results"])
    assert all("en_name" in item for item in data["results"])

    # Test case 2: Basic search in Hebrew
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "תפוח", "lang": "he"})
    print("\nHebrew Search Response:")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert all("primary_name" in item for item in data["results"])
    assert all("he_name" in item for item in data["results"])

    # Test case 3: Basic search in Spanish
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "manzana", "lang": "es"})
    print("\nSpanish Search Response:")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert all("primary_name" in item for item in data["results"])
    assert all("es_name" in item for item in data["results"])

    # Test case 4: Basic search in Russian
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "яблоко", "lang": "ru"})
    print("\nRussian Search Response:")
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    assert all("primary_name" in item for item in data["results"])
    assert all("ru_name" in item for item in data["results"])

def test_find_ingredient_by_name_invalid_lang():
    """Test finding ingredients with invalid language"""
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "apple", "lang": "invalid"})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Unsupported language" in data["detail"]

def test_find_ingredient_by_name_empty_query():
    """Test finding ingredients with empty query"""
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "", "lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)

def test_find_ingredient_by_name_no_results():
    """Test finding ingredients with no matching results"""
    response = requests.get(f"{BASE_URL}/find_ingredient_by_name", params={"query": "xyz123nonexistent", "lang": "en"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 0
