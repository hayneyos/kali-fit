import pytest
import requests
from datetime import datetime

# Base URL for the API
PROD_BASE_URL = "https://for-checking.live/api/"  # Update this with your actual production URL

def test_calc_bmi():
    """Test the BMI calculation endpoint"""
    response = requests.get(
        f"{PROD_BASE_URL}/calc_bmi",
        params={
            "weight": 70,
            "height": 170,
            "birthDate": "1990-01-01",
            "gender": "gender_male",
            "activity_level": "moderate",
            "dietType": "balanced",
            "weekly_goal": 0.5,
            "main_goal": "weight_loss",
            "weight_goal": 65,
            "social": "private"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "bmi" in data
    assert "bmr" in data
    assert "tdee" in data
    assert "daily_calories" in data
    assert "protein_g" in data
    assert "carbs_g" in data
    assert "fats_g" in data

def test_track_client():
    """Test the client tracking endpoint"""
    response = requests.post(
        f"{PROD_BASE_URL}/track",
        json={
            "email": "test@example.com",
            "device_id": "test_device_123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "device_id" in data
    assert "ip" in data

def test_calc_bmi_missing_params():
    """Test BMI calculation with missing parameters"""
    response = requests.get(f"{PROD_BASE_URL}/calc_bmi")
    assert response.status_code == 422
    error_data = response.json()
    # Check if error message contains information about missing parameters
    assert any(key in str(error_data) for key in ["Missing", "required", "parameters"])

def test_calc_bmi_invalid_data():
    """Test BMI calculation with invalid data"""
    response = requests.get(
        f"{PROD_BASE_URL}/calc_bmi",
        params={
            "weight": -70,  # Invalid negative weight
            "height": 170,
            "birthDate": "1990-01-01",
            "gender": "gender_male",
            "activity_level": "moderate",
            "dietType": "balanced",
            "weekly_goal": 0.5,
            "main_goal": "weight_loss",
            "weight_goal": 65,
            "social": "private"
        }
    )
    assert response.status_code == 400
    error_data = response.json()
    # Check if error message contains information about invalid weight
    assert any(key in str(error_data) for key in ["weight", "positive", "invalid"])

def test_track_client_missing_data():
    """Test client tracking with missing data"""
    response = requests.post(f"{PROD_BASE_URL}/track", json={})
    assert response.status_code == 200  # Should still work with empty data
    data = response.json()
    assert "email" in data
    assert "device_id" in data
    assert "ip" in data

def test_store_wizard_data():
    """Test storing wizard data"""
    wizard_data = {
        "discovery_source": "Friend",
        "gender": "gender_male",
        "weight": 70,
        "height": 170,
        "birth_date": "1990-01-01",
        "main_goal": "lose",
        "diet_type": "balanced",
        "weight_goal": 65,
        "workout_frequency": "3-4",
        "goal_pace": "balanced",
        "email": "test@example.com",
        "device_id": "test_device_123",
        "social": "private",
        "notifications_enabled": True,
        "health_data_connected": False
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/store_wizard_data",
        json=wizard_data
    )
    assert response.status_code == 200
    data = response.json()
    
    # Check user data
    assert "user_data" in data
    assert data["user_data"]["weight"] == 70
    assert data["user_data"]["height"] == 170
    
    # Check calculated metrics
    assert "calculated_metrics" in data
    assert "bmi" in data["calculated_metrics"]
    assert "bmr" in data["calculated_metrics"]
    assert "tdee" in data["calculated_metrics"]
    assert "daily_calories" in data["calculated_metrics"]
    assert "weekly_goal_kg" in data["calculated_metrics"]
    assert "macros" in data["calculated_metrics"]
    
    # Check timeline
    assert "timeline" in data
    assert "start_date" in data["timeline"]
    assert "estimated_completion" in data["timeline"]

def test_store_wizard_data_missing_required():
    """Test storing wizard data with missing required fields"""
    wizard_data = {
        "discovery_source": "Friend",
        "gender": "gender_male",
        # Missing weight and height
        "birth_date": "1990-01-01",
        "main_goal": "lose",
        "diet_type": "balanced",
        "weight_goal": 65,
        "workout_frequency": "3-4",
        "goal_pace": "balanced"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/store_wizard_data",
        json=wizard_data
    )
    assert response.status_code == 400

def test_store_wizard_data_invalid_values():
    """Test storing wizard data with invalid values"""
    wizard_data = {
        "discovery_source": "Friend",
        "gender": "gender_male",
        "weight": -70,  # Invalid negative weight
        "height": 170,
        "birth_date": "1990-01-01",
        "main_goal": "lose",
        "diet_type": "balanced",
        "weight_goal": 65,
        "workout_frequency": "3-4",
        "goal_pace": "balanced"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/store_wizard_data",
        json=wizard_data
    )
    assert response.status_code == 400

def test_store_wizard_data_optional_fields():
    """Test storing wizard data with only required fields"""
    wizard_data = {
        "discovery_source": "Friend",
        "gender": "gender_male",
        "weight": 70,
        "height": 170,
        "birth_date": "1990-01-01",
        "main_goal": "lose",
        "diet_type": "balanced",
        "weight_goal": 65,
        "workout_frequency": "3-4",
        "goal_pace": "balanced"
        # No optional fields
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/store_wizard_data",
        json=wizard_data
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_data" in data
    assert "calculated_metrics" in data
    assert "timeline" in data

def test_sync_data_invalid_date_range():
    """Test syncing data with invalid date range"""
    sync_data = {
        "platform": "google_fit",
        "access_token": "mock_google_fit_token",
        "device_id": "test_device_123",
        "start_date": "2024-03-20",  # End date before start date
        "end_date": "2024-03-13"
    }
    
    response = requests.post(
        f"{PROD_BASE_URL}/sync_data",
        json=sync_data
    )
    assert response.status_code == 422
    assert "End date cannot be before start date" in response.text 