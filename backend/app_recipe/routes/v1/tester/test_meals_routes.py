import pytest
import requests
from datetime import datetime

# Create te

PROD_BASE_URL = "https://for-checking.live/api/"

def print_json_response(response):
    try:
        print("JSON Response:", response.json())
    except Exception:
        print("Non-JSON Response:", response.text)

def test_calc_water_basic():
    """Test basic water calculation with only weight"""
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert "recommended_ml" in data
    assert "calculation_details" in data
    assert data["recommended_ml"] == 2450  # 70 * 35

def test_calc_water_with_age():
    """Test water calculation with age adjustments"""
    # Test young adult
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "age": 25})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2450  # 70 * 35 * 1.0

    # Test middle-aged adult
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "age": 40})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2327  # 70 * 35 * 0.95 (rounded down)

    # Test older adult
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "age": 60})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2205  # 70 * 35 * 0.9

def test_calc_water_with_gender():
    """Test water calculation with gender adjustments"""
    # Test male
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "gender": "male"})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2695  # 70 * 35 * 1.1

    # Test female
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "gender": "female"})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2450  # 70 * 35 * 1.0

def test_calc_water_with_temperature():
    """Test water calculation with temperature adjustments"""
    # Test normal temperature
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "temperature": 20})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2450  # 70 * 35

    # Test high temperature
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "temperature": 30})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_ml"] == 2572  # 70 * 35 * (1 + (30-25)*0.01)

def test_calc_water_all_factors():
    """Test water calculation with all factors"""
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "age": 40, "gender": "male", "temperature": 30})
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    expected = int(70 * 35 * 0.95 * 1.1 * (1 + (30-25)*0.01))
    assert data["recommended_ml"] == expected

def test_calc_water_invalid_inputs():
    """Test water calculation with invalid inputs"""
    # Test negative weight
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": -70})
    print_json_response(response)
    assert response.status_code == 200  # Currently accepts negative weights

    # Test zero weight
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 0})
    print_json_response(response)
    assert response.status_code == 200  # Currently accepts zero weight

    # Test invalid gender
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "gender": "invalid"})
    print_json_response(response)
    assert response.status_code == 200  # Should still work, just ignore invalid gender

    # Test negative temperature
    response = requests.get(f"{PROD_BASE_URL}/calc_water", params={"weight": 70, "temperature": -10})
    print_json_response(response)
    assert response.status_code == 200  # Should still work, just ignore negative temp

def test_take_water_basic():
    """Test basic water intake logging"""
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "amount": 250,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "test_user"
    assert data["drank_ml"] == 250
    assert data["left_ml"] == 2200  # 2450 - 250
    assert data["recommended_ml"] == 2450

def test_take_water_multiple_times():
    """Test logging multiple water intakes for the same user"""
    # First intake
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user2",
        "amount": 250,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["drank_ml"] == 250

    # Second intake
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user2",
        "amount": 300,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["drank_ml"] == 550  # 250 + 300

def test_take_water_all_factors():
    """Test water intake logging with all factors"""
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user3",
        "amount": 250,
        "weight": 70,
        "age": 40,
        "gender": "male",
        "temperature": 30
    })
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert "inputs" in data
    assert data["inputs"]["weight"] == 70
    assert data["inputs"]["age"] == 40
    assert data["inputs"]["gender"] == "male"
    assert data["inputs"]["temperature"] == 30

def test_take_water_missing_required():
    """Test water intake logging with missing required fields"""
    # Missing user_id
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "amount": 250,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 400

    # Missing amount
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 400

    # Missing weight
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "amount": 250
    })
    print_json_response(response)
    assert response.status_code == 400

def test_take_water_invalid_inputs():
    """Test water intake logging with invalid inputs"""
    # Negative amount
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "amount": -250,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 400  # API correctly rejects negative amounts

    # Zero amount
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "amount": 0,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 400  # API correctly rejects zero amounts

    # Negative weight
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user",
        "amount": 250,
        "weight": -70
    })
    print_json_response(response)
    assert response.status_code == 400  # API correctly rejects negative weights

def test_take_water_exceeds_recommended():
    """Test water intake logging when exceeding recommended amount"""
    response = requests.post(f"{PROD_BASE_URL}/take_water", json={
        "user_id": "test_user4",
        "amount": 3000,
        "weight": 70
    })
    print_json_response(response)
    assert response.status_code == 200
    data = response.json()
    assert data["drank_ml"] == 3000
    assert data["left_ml"] == 0  # Should not go negative
    assert data["recommended_ml"] == 2450


def test_add_meal_invalid_date():
    """Test adding a meal with invalid date format"""
    add_resp = requests.post(
        f"{PROD_BASE_URL}/add_meal_for_date",
        json={
            "user_id": "test_user_invalid_date",
            "date": "2024-13-40",
            "meal": {"name": "Invalid Date Meal"}
        }
    )
    print_json_response(add_resp)
    assert add_resp.status_code == 422
    assert "Invalid date format" in add_resp.text


def test_add_meal_missing_fields():
    """Test adding a meal with missing required fields"""
    add_resp = requests.post(
        f"{PROD_BASE_URL}/add_meal_for_date",
        json={
            "date": "2024-01-01",
            "meal": {"name": "Missing User"}
        }
    )
    print_json_response(add_resp)
    assert add_resp.status_code == 422
    add_resp2 = requests.post(
        f"{PROD_BASE_URL}/add_meal_for_date",
        json={
            "user_id": "test_user_missing_meal",
            "date": "2024-01-01"
        }
    )
    print_json_response(add_resp2)
    assert add_resp2.status_code == 422


def test_add_and_get_meal_for_date():
    """Test adding a meal and then fetching it for a user and date"""
    user_id = f"test_user_{datetime.utcnow().timestamp()}"
    date = datetime.now().strftime("%Y-%m-%d")
    meal_data = {
        "name": "Test Lunch",
        "calories": 555,
        "time": "12:30",
        "custom_field": "test_value"
    }
    # Add meal
    add_resp = requests.post(
        f"{PROD_BASE_URL}/add_meal_for_date",
        json={
            "user_id": user_id,
            "date": date,
            "meal": meal_data
        }
    )
    print_json_response(add_resp)
    assert add_resp.status_code == 200, add_resp.text
    add_result = add_resp.json()
    assert add_result["status"] == "success"
    assert add_result["meal"]["name"] == meal_data["name"]
    assert add_result["meal"]["user_id"] == user_id
    assert add_result["meal"]["date"] == date
    assert "meal_id" in add_result["meal"]

    # Get meals for date
    get_resp = requests.post(
        f"{PROD_BASE_URL}/get_meals_dashboard_for_date",
        json={
            "user_id": user_id,
            "date": date
        }
    )
    print_json_response(get_resp)
    assert get_resp.status_code == 200, get_resp.text
    get_result = get_resp.json()
    assert get_result["user_id"] == user_id
    assert get_result["date"] == date
    assert isinstance(get_result["meals"], list)
    assert any(m["name"] == meal_data["name"] for m in get_result["meals"])

def test_get_meals_invalid_date():
    """Test getting meals with invalid date format"""
    get_resp = requests.post(
        f"{PROD_BASE_URL}/get_meals_dashboard_for_date",
        json={
            "user_id": "test_user_invalid_date",
            "date": "2024-13-40"
        }
    )
    print_json_response(get_resp)
    assert get_resp.status_code == 422
    assert "Invalid date format" in get_resp.text

def test_get_multiple_meals_for_date():
    """Test adding multiple meals and fetching them as a list from the DB"""
    user_id = f"test_user_multi_{datetime.utcnow().timestamp()}"
    date = datetime.now().strftime("%Y-%m-%d")
    meal_data_1 = {"name": "Breakfast", "calories": 300, "time": "08:00"}
    meal_data_2 = {"name": "Lunch", "calories": 600, "time": "13:00"}
    meal_data_3 = {"name": "Dinner", "calories": 500, "time": "19:00"}
    # Add meals
    for meal in [meal_data_1, meal_data_2, meal_data_3]:
        add_resp = requests.post(
            f"{PROD_BASE_URL}/add_meal_for_date",
            json={
                "user_id": user_id,
                "date": date,
                "meal": meal
            }
        )
        print_json_response(add_resp)
        assert add_resp.status_code == 200, add_resp.text
    # Get meals for date
    get_resp = requests.post(
        f"{PROD_BASE_URL}/get_meals_dashboard_for_date",
        json={
            "user_id": user_id,
            "date": date
        }
    )
    print_json_response(get_resp)
    assert get_resp.status_code == 200, get_resp.text
    get_result = get_resp.json()
    assert get_result["user_id"] == user_id
    assert get_result["date"] == date
    assert isinstance(get_result["meals"], list)
    names = [m["name"] for m in get_result["meals"]]
    assert "Breakfast" in names
    assert "Lunch" in names
    assert "Dinner" in names

def test_add_and_get_meals_to_favorite():
    """Test adding a meal to favorites and fetching all favorites for a user"""
    user_id = f"test_fav_user_{datetime.utcnow().timestamp()}"
    meal_data = {
        "name": "Favorite Meal",
        "calories": 777,
        "time": "15:00",
        "custom_field": "favorite_test"
    }
    # Add meal to favorites
    add_resp = requests.post(
        f"{PROD_BASE_URL}/add_meals_to_favorite",
        json={
            "user_id": user_id,
            "meal": meal_data
        }
    )
    print_json_response(add_resp)
    assert add_resp.status_code == 200
    add_result = add_resp.json()
    assert add_result["status"] == "success"
    assert add_result["favorite"]["name"] == meal_data["name"]
    assert add_result["favorite"]["user_id"] == user_id
    assert "favorite_id" in add_result["favorite"]

    # Get all favorite meals for user
    get_resp = requests.post(
        f"{PROD_BASE_URL}/get_meals_from_favorite",
        json={
            "user_id": user_id
        }
    )
    print_json_response(get_resp)
    assert get_resp.status_code == 200
    get_result = get_resp.json()
    assert get_result["user_id"] == user_id
    assert isinstance(get_result["favorites"], list)
    assert any(fav["name"] == meal_data["name"] for fav in get_result["favorites"])

def test_add_meal_to_favorite_missing_fields():
    """Test adding a favorite meal with missing required fields"""
    add_resp = requests.post(
        f"{PROD_BASE_URL}/add_meals_to_favorite",
        json={
            "meal": {"name": "Missing User"}
        }
    )
    print_json_response(add_resp)
    assert add_resp.status_code == 422
    add_resp2 = requests.post(
        f"{PROD_BASE_URL}/add_meals_to_favorite",
        json={
            "user_id": "test_fav_missing_meal"
        }
    )
    print_json_response(add_resp2)
    assert add_resp2.status_code == 422

def test_get_meals_from_favorite_no_user():
    """Test getting favorite meals with missing user_id"""
    get_resp = requests.post(
        f"{PROD_BASE_URL}/get_meals_from_favorite",
        json={}
    )
    print_json_response(get_resp)
    assert get_resp.status_code == 422

