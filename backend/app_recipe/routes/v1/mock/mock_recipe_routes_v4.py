import logging
import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mock_recipe import (
    mock_get_recipe,
    mock_find_ingredient,
    mock_analyze_refrigerator,
    mock_get_uploaded_file,
    save_uploaded_file
)

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('mock_recipe_routes')

# Load environment variables
router = APIRouter()

@router.get("/get_recipe")
async def get_recipe(
        request: Request,
        lang: Optional[str] = None,
        difficulty: Optional[str] = None,
        ingredients: Optional[str] = None,
        diet_type: Optional[str] = None,
        min_calories: Optional[float] = None,
        max_calories: Optional[float] = None,
        min_proteins: Optional[float] = None,
        max_proteins: Optional[float] = None,
        max_prep_time: Optional[str] = None,
        min_carbs: Optional[float] = None,
        max_carbs: Optional[float] = None,
        min_fats: Optional[float] = None,
        max_fats: Optional[float] = None,
        limit: int = 10,
        skip: int = 0
):
    """
    Mock endpoint for getting recipes that returns saved response if available
    """
    try:
        return await mock_get_recipe(
            request=request,
            lang=lang,
            difficulty=difficulty,
            ingredients=ingredients,
            diet_type=diet_type,
            min_calories=min_calories,
            max_calories=max_calories,
            min_proteins=min_proteins,
            max_proteins=max_proteins,
            max_prep_time=max_prep_time,
            min_carbs=min_carbs,
            max_carbs=max_carbs,
            min_fats=min_fats,
            max_fats=max_fats,
            limit=limit,
            skip=skip
        )
    except Exception as e:
        error_msg = f"Error in mock get_recipe: {str(e)}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

@router.get("/find_ingredient_by_name")
async def find_ingredient_by_name(
        query: str,
        lang: str,
        request: Request = None
):
    """
    Mock endpoint for finding ingredients that returns saved response if available
    """
    try:
        return await mock_find_ingredient(
            query=query,
            lang=lang,
            request=request
        )
    except Exception as e:
        error_msg = f"Error in mock find_ingredient: {str(e)}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

@router.post("/find_ingredient_by_image")
async def analyze_refrigerator(
        file: UploadFile = File(..., description="The image file to analyze"),
        request: Request = None
):
    """
    Mock endpoint for analyzing refrigerator images that returns saved response if available
    """
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Save the uploaded file to mock location
        await file.seek(0)
        save_uploaded_file(file, file.filename)

        return await mock_analyze_refrigerator(
            file=file,
            request=request
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error in mock analyze_refrigerator: {str(e)}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

@router.get("/uploads/{filename}")
async def uploaded_file(filename: str):
    """
    Mock endpoint for retrieving uploaded files
    """
    try:
        return await mock_get_uploaded_file(filename)
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error in mock uploaded_file: {str(e)}"
        logger.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        ) 