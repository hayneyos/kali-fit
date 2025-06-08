import logging
import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mock_utils import save_mock_data, load_mock_data
from backend.app_recipe.consts import UPLOAD_FOLDER_APP

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('mock_model_routes')

router = APIRouter(prefix="/mock")

@router.post("/predict_meals")
async def mock_proxy_openai(request: Request):
    """Mock endpoint for OpenAI proxy that returns saved response if available"""

    # Try to load existing mock data
    mock_data = load_mock_data("predict_meals")
    return mock_data
       

@router.post("/upload")
async def mock_upload_file(file: UploadFile = File(...)):
    """Mock endpoint for file upload that returns saved response if available"""
    try:
        # Try to load existing mock data
        mock_data = load_mock_data("upload")
        if mock_data:
            return mock_data

        # Create upload directory if it doesn't exist
        os.makedirs(UPLOAD_FOLDER_APP, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(UPLOAD_FOLDER_APP, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create sample response
        sample_response = {"filename": file.filename}

        # Save the sample response
        save_mock_data("upload", sample_response)
        return sample_response

    except Exception as e:
        error_msg = f"Error in mock upload_file: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/uploads/{filename}")
async def mock_uploaded_file(filename: str):
    """Mock endpoint for retrieving uploaded files"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER_APP, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(file_path)
    except Exception as e:
        error_msg = f"Error in mock uploaded_file: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg) 