import requests
import pytest
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base URL for the API
PROD_BASE_URL = "https://for-checking.live/api/"  # Update this with your actual production URL

def test_sync_health_data_google_fit():
    """Test syncing health data from Google Fit"""
    sync_data = {
        "platform": "google_fit",
        "access_token": "mock_google_fit_token",
        "device_id": "test_device_123",
        "start_date": "2024-03-13",
        "end_date": "2024-03-20"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_health_data",
        json=sync_data
    )
    logger.info(f"Google Fit sync response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "status" in data
    assert data["status"] == "success"
    assert "platform" in data
    assert data["platform"] == "google_fit"
    assert "sync_date" in data
    assert "date_range" in data
    assert "health_data" in data
    
    # Check health data fields
    health_data = data["health_data"]
    assert "steps" in health_data
    assert "distance" in health_data
    assert "calories" in health_data
    assert "heart_rate" in health_data
    assert "sleep_duration" in health_data
    assert "active_minutes" in health_data
    assert "water_intake" in health_data

def test_sync_health_data_apple_health():
    """Test syncing health data from Apple Health"""
    sync_data = {
        "platform": "apple_health",
        "access_token": "mock_apple_health_token",
        "device_id": "test_device_123",
        "start_date": "2024-03-13",
        "end_date": "2024-03-20"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_health_data",
        json=sync_data
    )
    logger.info(f"Apple Health sync response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "status" in data
    assert data["status"] == "success"
    assert "platform" in data
    assert data["platform"] == "apple_health"
    assert "sync_date" in data
    assert "date_range" in data
    assert "health_data" in data

def test_sync_health_data_invalid_dates():
    """Test syncing health data with invalid date range"""
    sync_data = {
        "platform": "google_fit",
        "access_token": "mock_google_fit_token",
        "device_id": "test_device_123",
        "start_date": "2024-03-20",  # End date before start date
        "end_date": "2024-03-13"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_health_data",
        json=sync_data
    )
    logger.info(f"Invalid dates response status: {response.status_code}")
    logger.info(f"Invalid dates response body: {response.text}")
    assert response.status_code == 422
    assert "End date cannot be before start date" in response.text

def test_sync_health_data_missing_required():
    """Test syncing health data with missing required fields"""
    sync_data = {
        "platform": "google_fit",
        # Missing access_token and device_id
        "start_date": "2024-03-13",
        "end_date": "2024-03-20"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_health_data",
        json=sync_data
    )
    logger.info(f"Missing required fields response: {response.status_code} - {response.text}")
    assert response.status_code == 422

def test_sync_health_data_invalid_platform():
    """Test syncing health data with invalid platform"""
    sync_data = {
        "platform": "invalid_platform",
        "access_token": "mock_token",
        "device_id": "test_device_123",
        "start_date": "2024-03-13",
        "end_date": "2024-03-20"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_health_data",
        json=sync_data
    )
    logger.info(f"Invalid platform response: {response.status_code} - {response.text}")
    assert response.status_code == 422

def test_health_data_status_google_fit():
    """Test getting health data sync status for Google Fit"""
    response = requests.get(
        f"{PROD_BASE_URL}/health_data_status",
        params={
            "device_id": "test_device_123",
            "platform": "google_fit"
        }
    )
    logger.info(f"Google Fit status response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "status" in data
    assert data["status"] == "success"
    assert "device_id" in data
    assert data["device_id"] == "test_device_123"
    assert "sync_status" in data
    
    # Check sync status fields
    sync_status = data["sync_status"]
    assert "last_sync" in sync_status
    assert "sync_status" in sync_status
    assert "data_points" in sync_status
    assert "platform" in sync_status
    assert sync_status["platform"] == "google_fit"

def test_health_data_status_apple_health():
    """Test getting health data sync status for Apple Health"""
    response = requests.get(
        f"{PROD_BASE_URL}/health_data_status",
        params={
            "device_id": "test_device_123",
            "platform": "apple_health"
        }
    )
    logger.info(f"Apple Health status response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "status" in data
    assert data["status"] == "success"
    assert "device_id" in data
    assert data["device_id"] == "test_device_123"
    assert "sync_status" in data
    assert data["sync_status"]["platform"] == "apple_health"

def test_health_data_status_missing_params():
    """Test getting health data status with missing parameters"""
    response = requests.get(
        f"{PROD_BASE_URL}/health_data_status",
        params={
            "device_id": "test_device_123"
            # Missing platform parameter
        }
    )
    logger.info(f"Missing params response: {response.status_code} - {response.text}")
    assert response.status_code == 422

def test_health_data_status_invalid_platform():
    """Test getting health data status with invalid platform"""
    response = requests.get(
        f"{PROD_BASE_URL}/health_data_status",
        params={
            "device_id": "test_device_123",
            "platform": "invalid_platform"
        }
    )
    logger.info(f"Invalid platform status response: {response.status_code} - {response.text}")
    assert response.status_code == 422 