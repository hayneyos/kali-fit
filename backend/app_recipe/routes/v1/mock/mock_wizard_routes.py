import logging
import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mock_utils import save_mock_data, load_mock_data

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('mock_wizard_routes')

router = APIRouter()

@router.get("/calc_bmi")
async def mock_calc_bmi(
        request: Request,
        weight: Optional[float] = None,
        height: Optional[float] = None,
        birthDate: Optional[str] = None,
        gender: Optional[str] = None,
        activity_level: str = "moderate",
        dietType: Optional[str] = None,
        weekly_goal: Optional[float] = None,
        main_goal: Optional[str] = None,
        weight_goal: Optional[float] = None,
        social: Optional[str] = None
):
    """Mock endpoint for BMI calculation that returns saved response if available"""
    try:
        # Try to load existing mock data
        mock_data = load_mock_data("calc_bmi")
        if mock_data:
            return mock_data

        # If no mock data exists, create a sample response
        sample_response = {
            "bmi": 24.5,
            "bmr": 1800,
            "tdee": 2700,
            "daily_calories": 2500,
            "recommended_min": 2000,
            "recommended_max": 3000,
            "weight": weight or 70,
            "height": height or 170,
            "age": 30,
            "gender": gender or "male",
            "diet_type": dietType or "balanced",
            "weekly_goal_kg": weekly_goal or 0.5,
            "main_goal": main_goal or "weight_loss",
            "weight_goal": weight_goal or 65,
            "social": social or "private",
            "protein_g": 150,
            "carbs_g": 250,
            "fats_g": 83
        }

        # Save the sample response
        save_mock_data("calc_bmi", sample_response)
        return sample_response

    except Exception as e:
        error_msg = f"Error in mock calc_bmi: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/track")
async def mock_track_client(request: Request):
    """Mock endpoint for tracking client that returns saved response if available"""
    try:
        # Try to load existing mock data
        mock_data = load_mock_data("track")
        if mock_data:
            return mock_data

        # If no mock data exists, create a sample response
        body = await request.json()
        sample_response = {
            "email": {"value": body.get("email", "test@example.com"), "count": 1},
            "device_id": {"value": body.get("device_id", "test_device"), "count": 1},
            "ip": {"value": request.client.host, "count": 1}
        }

        # Save the sample response
        save_mock_data("track", sample_response)
        return sample_response

    except Exception as e:
        error_msg = f"Error in mock track_client: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg) 