import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.services.wrapper_db.WrapperService import count_requests_in_db
from backend.app_recipe.utils.wizard_utils import calculate_age, calculate_bmi, calculate_bmr, calculate_tdee, \
    adjust_calories, get_calorie_bounds, calculate_macros, WizardData, calculate_completion_date

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('wizard_routes')

# Load environment variables
router = APIRouter()


@router.get("/calc_bmi")
async def calc_bmi(
        request: Request,
        weight: Optional[float] = None,
        height: Optional[float] = None,
        birthDate: Optional[str] = None,
        gender: Optional[str] = None,
        activity_level: str = "moderate",
        dietType: Optional[str] = None,
        weekly_goal: Optional[float] = None,  # in kg/week, e.g. -0.5 or +0.9
        main_goal: Optional[str] = None,
        weight_goal: Optional[float] = None,
        social: Optional[str] = None
):
    required_fields = {
        "weight": weight,
        "height": height,
        "birthDate": birthDate,
        "gender": gender,
        "main_goal": main_goal,
        "dietType": dietType,
        "weight_goal": weight_goal,
        "social": social,
    }

    missing_fields = [key for key, val in required_fields.items() if val is None]
    if missing_fields:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required parameters: {', '.join(missing_fields)}"
        )

    # Validate weight and height are positive
    if weight <= 0:
        raise HTTPException(status_code=400, detail="Weight must be positive")
    if height <= 0:
        raise HTTPException(status_code=400, detail="Height must be positive")

    try:
        gender_clean = gender.split(".")[-1].replace("gender_", "")
        age = calculate_age(birthDate)

        bmi = calculate_bmi(weight, height)
        bmr = calculate_bmr(gender_clean, weight, height, age)
        tdee = calculate_tdee(bmr, activity_level)
        daily_calories = adjust_calories(tdee, weekly_goal or 0.0)

        min_calories, max_calories = get_calorie_bounds(age, gender_clean, activity_level)

        protein_g, carbs_g, fats_g = calculate_macros(daily_calories)

        return {
            "bmi": bmi,
            "bmr": bmr,
            "tdee": tdee,
            "daily_calories": daily_calories,
            "recommended_min": min_calories,
            "recommended_max": max_calories,
            "weight": weight,
            "height": height,
            "age": int(age),
            "gender": gender_clean,
            "diet_type": dietType,
            "weekly_goal_kg": weekly_goal,
            "main_goal": main_goal,
            "weight_goal": weight_goal,
            "social": social,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fats_g": fats_g
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing data: {str(e)}")


@router.post("/track")
async def track_client(request: Request):
    try:
        body = await request.json()

        email = body.get("email")
        device_id = body.get("device_id")
        ip_address = request.client.host

        email_count = await count_requests_in_db("email", email, logger)
        device_count = await count_requests_in_db("device_id", device_id, logger)
        ip_address_count = await count_requests_in_db("ip_address", ip_address, logger)

        return {
            "email": {"value": email, "count": email_count},
            "device_id": {"value": device_id, "count": device_count},
            "ip": {"value": ip_address, "count": ip_address_count}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error tracking client: {str(e)}")


@router.post("/store_wizard_data")
async def store_wizard_data(request: Request):
    """
    Store wizard data collected during onboarding.
    
    Args:
        request (Request): JSON body containing wizard data
    
    Returns:
        dict: Contains stored data and calculated metrics
    """
    try:
        data = await request.json()
        wizard_data = WizardData(**data)

        # Calculate metrics
        age = calculate_age(wizard_data.birth_date)
        bmi = calculate_bmi(wizard_data.weight, wizard_data.height)
        bmr = calculate_bmr(wizard_data.gender, wizard_data.weight, wizard_data.height, age)

        # Map workout frequency to activity level
        activity_level_map = {
            "0": "sedentary",
            "1-2": "light",
            "3-4": "moderate",
            "5+": "active"
        }
        activity_level = activity_level_map.get(wizard_data.workout_frequency, "moderate")

        tdee = calculate_tdee(bmr, activity_level)

        # Calculate weekly goal based on goal pace
        weekly_goal_map = {
            "slow": 0.25,  # 0.25 kg per week
            "balanced": 0.5,  # 0.5 kg per week
            "fast": 0.75  # 0.75 kg per week
        }
        weekly_goal = weekly_goal_map.get(wizard_data.goal_pace, 0.5)

        # Adjust calories based on goal
        if wizard_data.main_goal == "lose":
            weekly_goal = -weekly_goal
        elif wizard_data.main_goal == "maintain":
            weekly_goal = 0

        daily_calories = adjust_calories(tdee, weekly_goal)
        protein_g, carbs_g, fats_g = calculate_macros(daily_calories)

        # Store in database (implement your database storage logic here)
        # For now, we'll just return the calculated data
        stored_data = {
            "user_data": wizard_data.dict(),
            "calculated_metrics": {
                "bmi": bmi,
                "bmr": bmr,
                "tdee": tdee,
                "daily_calories": daily_calories,
                "weekly_goal_kg": weekly_goal,
                "macros": {
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fats_g": fats_g
                }
            },
            "timeline": {
                "start_date": datetime.now().strftime("%Y-%m-%d"),
                "estimated_completion": calculate_completion_date(
                    wizard_data.weight,
                    wizard_data.weight_goal,
                    weekly_goal
                )
            }
        }

        return JSONResponse(content=stored_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing wizard data: {str(e)}")
