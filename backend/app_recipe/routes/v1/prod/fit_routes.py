from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator, model_validator
from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.services.wrapper_db.WrapperService import count_requests_in_db

# Configure logger
logger = get_logger(__name__)

router = APIRouter()

# Valid platform types
PlatformType = Literal["google_fit", "apple_health"]

class HealthSyncRequest(BaseModel):
    platform: PlatformType = Field(..., description="Health platform (google_fit/apple_health)")
    access_token: str = Field(..., description="OAuth access token for the platform")
    device_id: str = Field(..., description="User's device ID")
    start_date: Optional[str] = Field(None, description="Start date for data sync (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date for data sync (YYYY-MM-DD)")

    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return v

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            start = datetime.strptime(values['start_date'], "%Y-%m-%d")
            end = datetime.strptime(v, "%Y-%m-%d")
            if end < start:
                raise ValueError("End date cannot be before start date")
        return v

    @model_validator(mode='after')
    def validate_required_fields(self):
        if not self.access_token:
            raise ValueError("access_token is required")
        if not self.device_id:
            raise ValueError("device_id is required")
        return self

class HealthData(BaseModel):
    steps: int = Field(..., description="Number of steps")
    distance: float = Field(..., description="Distance in meters")
    calories: float = Field(..., description="Calories burned")
    heart_rate: Optional[float] = Field(None, description="Average heart rate")
    sleep_duration: Optional[float] = Field(None, description="Sleep duration in hours")
    active_minutes: Optional[int] = Field(None, description="Active minutes")
    water_intake: Optional[float] = Field(None, description="Water intake in ml")

@router.post("/sync_health_data")
async def sync_health_data(request: Request, sync_request: HealthSyncRequest):
    """
    Sync health data from Google Fit or Apple Health
    
    Args:
        request: FastAPI request object
        sync_request: HealthSyncRequest object containing platform and auth details
        
    Returns:
        JSONResponse with synced health data
    """
    try:
        # Log request
        logger.info(f"Health sync request received for platform: {sync_request.platform}")
        
        # Get date range
        start_date = datetime.strptime(sync_request.start_date, "%Y-%m-%d") if sync_request.start_date else datetime.now() - timedelta(days=7)
        end_date = datetime.strptime(sync_request.end_date, "%Y-%m-%d") if sync_request.end_date else datetime.now()
            
        # Mock health data (replace with actual API calls)
        health_data = {
            "steps": 8500,
            "distance": 6500.0,  # meters
            "calories": 450.0,
            "heart_rate": 72.0,
            "sleep_duration": 7.5,
            "active_minutes": 45,
            "water_intake": 2000.0  # ml
        }
        
        return JSONResponse({
            "status": "success",
            "platform": sync_request.platform,
            "sync_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "health_data": health_data
        })
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error syncing health data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error syncing health data: {str(e)}")

@router.get("/health_data_status")
async def get_health_data_status(request: Request, device_id: str, platform: PlatformType):
    """
    Get the sync status of health data for a device
    
    Args:
        request: FastAPI request object
        device_id: User's device ID
        platform: Health platform (google_fit/apple_health)
        
    Returns:
        JSONResponse with sync status
    """
    try:
        # Log request
        logger.info(f"Health data status request received for device: {device_id}")
        
        # Mock sync status (replace with actual database check)
        sync_status = {
            "last_sync": "2024-03-20 15:30:00",
            "sync_status": "success",
            "data_points": 150,
            "platform": platform
        }
        
        return JSONResponse({
            "status": "success",
            "device_id": device_id,
            "sync_status": sync_status
        })
        
    except Exception as e:
        logger.error(f"Error getting health data status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting health data status: {str(e)}") 