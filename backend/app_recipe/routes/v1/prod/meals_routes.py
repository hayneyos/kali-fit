from pydantic import BaseModel, Field
import logging
import os
from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client
from bson import ObjectId

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('recipe_routes')

# Load environment variables
router = APIRouter()


# In-memory water log: {user_id: {date: total_ml}}
water_log = {}

def calc_water_intake(weight_kg: float, age: Optional[int] = None, gender: Optional[str] = None, temperature_c: Optional[float] = None) -> int:
    """
    Calculate recommended daily water intake in milliliters based on scientific guidelines.
    
    Formula based on:
    1. Base Formula (35ml/kg): WHO, Mayo Clinic, and EFSA guidelines
    2. Age Adjustment: Physiological changes in water retention and kidney function
    3. Gender Adjustment: U.S. National Academies of Sciences (2004) recommendations
    4. Temperature Adjustment: Military and sports hydration studies
    
    Sources:
    - WHO Guidelines for Drinking-water Quality
    - Mayo Clinic: Water: How much should you drink every day?
    - EFSA: Scientific Opinion on Dietary Reference Values for water
    - U.S. National Academies of Sciences (2004): Dietary Reference Intakes for Water
    
    Args:
        weight_kg (float): Body weight in kilograms
        age (Optional[int]): Age in years
        gender (Optional[str]): 'male' or 'female'
        temperature_c (Optional[float]): Ambient temperature in Celsius
    
    Returns:
        int: Recommended daily water intake in milliliters
    """
    # Base calculation: 35ml per kg of body weight
    # Source: WHO, Mayo Clinic, and EFSA guidelines
    base_ml = weight_kg * 35

    # Age-based adjustments
    # Source: Physiological changes in water retention and kidney function
    if age:
        if age < 30:
            base_ml *= 1.0  # Full hydration need for young adults
        elif age < 55:
            base_ml *= 0.95  # Slightly reduced need for middle-aged adults
        else:
            base_ml *= 0.9  # Further reduced need for older adults

    # Gender-based adjustments
    # Source: U.S. National Academies of Sciences (2004)
    # Men: ~3.7L/day, Women: ~2.7L/day
    if gender and gender.lower() == "male":
        base_ml *= 1.1  # 10% increase for males due to higher lean muscle mass
    elif gender and gender.lower() == "female":
        base_ml *= 1.0  # Base calculation for females

    # Temperature-based adjustments
    # Source: Military and sports hydration studies
    # Additional 100-150ml per degree Celsius above 25°C
    if temperature_c and temperature_c > 25:
        # 1% increase per degree above 25°C
        base_ml *= 1 + (temperature_c - 25) * 0.01

    return int(base_ml)

@router.get("/calc_water")
async def calc_water(
    weight: float,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    temperature: Optional[float] = None
):
    """
    Calculate recommended daily water intake based on scientific guidelines.
    
    Args:
        weight (float): Body weight in kilograms
        age (Optional[int]): Age in years
        gender (Optional[str]): 'male' or 'female'
        temperature (Optional[float]): Ambient temperature in Celsius
    
    Returns:
        dict: Contains recommended water intake in milliliters and calculation details
    """
    recommended = calc_water_intake(weight, age, gender, temperature)
    return {
        "recommended_ml": recommended,
        "calculation_details": {
            "base_formula": "35ml per kg of body weight",
            "sources": [
                "WHO Guidelines for Drinking-water Quality",
                "Mayo Clinic: Water: How much should you drink every day?",
                "EFSA: Scientific Opinion on Dietary Reference Values for water",
                "U.S. National Academies of Sciences (2004): Dietary Reference Intakes for Water"
            ],
            "adjustments_applied": {
                "age": age is not None,
                "gender": gender is not None,
                "temperature": temperature is not None
            }
        }
    }

@router.post("/take_water")
async def take_water(request: Request):
    """
    Log water intake and return how much is left to drink today.
    
    Args:
        request (Request): JSON body containing:
            - user_id (str): Unique identifier for the user
            - amount (float): Amount of water consumed in milliliters
            - weight (float): User's weight in kilograms
            - age (Optional[int]): User's age in years
            - gender (Optional[str]): User's gender ('male' or 'female')
            - temperature (Optional[float]): Ambient temperature in Celsius
    
    Returns:
        dict: Contains water intake statistics and remaining amount
    """
    data = await request.json()
    user_id = data.get("user_id")
    amount = data.get("amount")  # in ml
    weight = data.get("weight")  # in kg
    age = data.get("age")
    gender = data.get("gender")
    temperature = data.get("temperature")  # in Celsius

    if not user_id or not amount or not weight:
        raise HTTPException(status_code=400, detail="user_id, amount, and weight are required")

    # Validate amount is positive
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    # Validate weight is positive
    if weight <= 0:
        raise HTTPException(status_code=400, detail="weight must be positive")

    today = datetime.now().strftime("%Y-%m-%d")

    if user_id not in water_log:
        water_log[user_id] = {}
    if today not in water_log[user_id]:
        water_log[user_id][today] = 0

    water_log[user_id][today] += amount
    drank = water_log[user_id][today]
    recommended = calc_water_intake(weight, age, gender, temperature)
    left = max(recommended - drank, 0)

    return {
        "user_id": user_id,
        "drank_ml": drank,
        "left_ml": left,
        "recommended_ml": recommended,
        "inputs": {
            "weight": weight,
            "age": age,
            "gender": gender,
            "temperature": temperature
        },
        "calculation_details": {
            "base_formula": "35ml per kg of body weight",
            "sources": [
                "WHO Guidelines for Drinking-water Quality",
                "Mayo Clinic: Water: How much should you drink every day?",
                "EFSA: Scientific Opinion on Dietary Reference Values for water",
                "U.S. National Academies of Sciences (2004): Dietary Reference Intakes for Water"
            ]
        }
    }

class MealsDashboardRequest(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    date: str = Field(..., description="Date in YYYY-MM-DD format")

class Meal(BaseModel):
    meal_id: Optional[str]
    name: Optional[str]
    calories: Optional[float]
    time: Optional[str]
    # Add other relevant fields as needed

@router.post("/get_meals_dashboard_for_date")
async def get_meals_dashboard_for_date(request: Request, dashboard_request: MealsDashboardRequest):
    """
    Get all intake meals for a user on a specific date.
    Args:
        dashboard_request: Contains user_id and date
    Returns:
        List of all meals for the user on the given date
    """
    try:
        # Validate date format
        try:
            query_date = datetime.strptime(dashboard_request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

        # Connect to MongoDB
        client = get_mongo_client()
        db = client["users"]
        meals_collection = db["meals"]

        # Query meals for user and date
        meals_cursor = meals_collection.find({
            "user_id": dashboard_request.user_id,
            "date": dashboard_request.date
        })
        meals = []
        for meal in meals_cursor:
            meal["meal_id"] = str(meal.get("_id"))
            meal.pop("_id", None)
            # Convert any datetime fields to ISO string
            for k, v in meal.items():
                if isinstance(v, datetime):
                    meal[k] = v.isoformat()
            meals.append(meal)
        client.close()

        return JSONResponse({
            "user_id": dashboard_request.user_id,
            "date": dashboard_request.date,
            "meals": meals
        })
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching meals dashboard: {str(e)}")

class AddMealRequest(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    meal: dict = Field(..., description="Meal data as JSON object")

@router.post("/add_meal_for_date")
async def add_meal_for_date(request: Request, add_request: AddMealRequest):
    """
    Add a meal for a user on a specific date.
    Args:
        add_request: Contains user_id, date, and meal data
    Returns:
        Confirmation and the saved meal data
    """
    try:
        # Validate date format
        try:
            query_date = datetime.strptime(add_request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

        # Connect to MongoDB
        client = get_mongo_client()
        db = client["users"]
        meals_collection = db["meals"]

        # Prepare meal document
        meal_doc = add_request.meal.copy()
        meal_doc["user_id"] = add_request.user_id
        meal_doc["date"] = add_request.date
        meal_doc["created_at"] = datetime.utcnow()

        # Insert meal
        result = meals_collection.insert_one(meal_doc)
        meal_doc["meal_id"] = str(result.inserted_id)
        meal_doc.pop("_id", None)
        # Convert any ObjectId fields in meal_doc to str
        for k, v in meal_doc.items():
            if isinstance(v, ObjectId):
                meal_doc[k] = str(v)
        if "created_at" in meal_doc and isinstance(meal_doc["created_at"], datetime):
            meal_doc["created_at"] = meal_doc["created_at"].isoformat()
        client.close()

        return JSONResponse({
            "status": "success",
            "message": "Meal saved successfully.",
            "meal": meal_doc
        })
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving meal: {str(e)}")

class AddMealToFavoriteRequest(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")
    meal: dict = Field(..., description="Meal data as JSON object")

@router.post("/add_meals_to_favorite")
async def add_meals_to_favorite(request: Request, add_request: AddMealToFavoriteRequest):
    """
    Save a meal as favorite for a user.
    """
    try:
        client = get_mongo_client()
        db = client["users"]
        favorites_collection = db["favorite_meals"]

        meal_doc = add_request.meal.copy()
        meal_doc["user_id"] = add_request.user_id
        meal_doc["created_at"] = datetime.utcnow()

        result = favorites_collection.insert_one(meal_doc)
        meal_doc["favorite_id"] = str(result.inserted_id)
        meal_doc.pop("_id", None)
        for k, v in meal_doc.items():
            if isinstance(v, ObjectId):
                meal_doc[k] = str(v)
        if "created_at" in meal_doc and isinstance(meal_doc["created_at"], datetime):
            meal_doc["created_at"] = meal_doc["created_at"].isoformat()
        client.close()

        return JSONResponse({
            "status": "success",
            "message": "Meal added to favorites.",
            "favorite": meal_doc
        })
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving favorite meal: {str(e)}")

class GetFavoritesRequest(BaseModel):
    user_id: str = Field(..., description="User's unique identifier")

@router.post("/get_meals_from_favorite")
async def get_meals_from_favorite(request: Request, get_request: GetFavoritesRequest):
    """
    Get all favorite meals for a user.
    """
    try:
        client = get_mongo_client()
        db = client["users"]
        favorites_collection = db["favorite_meals"]

        favorites_cursor = favorites_collection.find({
            "user_id": get_request.user_id
        })
        favorites = []
        for fav in favorites_cursor:
            fav["favorite_id"] = str(fav.get("_id"))
            fav.pop("_id", None)
            for k, v in fav.items():
                if isinstance(v, datetime):
                    fav[k] = v.isoformat()
                if isinstance(v, ObjectId):
                    fav[k] = str(v)
            favorites.append(fav)
        client.close()

        return JSONResponse({
            "user_id": get_request.user_id,
            "favorites": favorites
        })
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching favorite meals: {str(e)}") 