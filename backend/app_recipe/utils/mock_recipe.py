import json
import os
import shutil
from typing import Optional, Dict, Any
from fastapi import Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from starlette.responses import FileResponse

# Path to store the mock data
MOCK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_data")
MOCK_RECIPE_FILE = os.path.join(MOCK_DATA_DIR, "recipe_response.json")
MOCK_INGREDIENT_FILE = os.path.join(MOCK_DATA_DIR, "ingredient_response.json")
MOCK_FRIDGE_FILE = os.path.join(MOCK_DATA_DIR, "fridge_response.json")
MOCK_UPLOADS_DIR = os.path.join(MOCK_DATA_DIR, "uploads")

def save_recipe_response(response_data: Dict[str, Any]) -> None:
    """
    Save the recipe API response to a JSON file
    
    Args:
        response_data (Dict[str, Any]): The response data to save
    """
    # Create mock_data directory if it doesn't exist
    os.makedirs(MOCK_DATA_DIR, exist_ok=True)
    
    # Save the response to file
    with open(MOCK_RECIPE_FILE, 'w', encoding='utf-8') as f:
        json.dump(response_data, f, ensure_ascii=False, indent=2)

def save_ingredient_response(response_data: Dict[str, Any]) -> None:
    """
    Save the ingredient API response to a JSON file
    
    Args:
        response_data (Dict[str, Any]): The response data to save
    """
    # Create mock_data directory if it doesn't exist
    os.makedirs(MOCK_DATA_DIR, exist_ok=True)
    
    # Save the response to file
    with open(MOCK_INGREDIENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(response_data, f, ensure_ascii=False, indent=2)

def save_fridge_response(response_data: Dict[str, Any]) -> None:
    """
    Save the refrigerator analysis API response to a JSON file
    
    Args:
        response_data (Dict[str, Any]): The response data to save
    """
    # Create mock_data directory if it doesn't exist
    os.makedirs(MOCK_DATA_DIR, exist_ok=True)
    
    # Save the response to file
    with open(MOCK_FRIDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(response_data, f, ensure_ascii=False, indent=2)

def save_uploaded_file(file: UploadFile, filename: str) -> str:
    """
    Save an uploaded file to the mock uploads directory
    
    Args:
        file (UploadFile): The uploaded file
        filename (str): The filename to save as
        
    Returns:
        str: The path where the file was saved
    """
    # Create uploads directory if it doesn't exist
    os.makedirs(MOCK_UPLOADS_DIR, exist_ok=True)
    
    # Save the file
    file_path = os.path.join(MOCK_UPLOADS_DIR, filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return file_path

async def mock_get_recipe(
    request: Request,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    ingredients: Optional[str] = None,
    diet_type: Optional[str] = None,
    max_prep_time: Optional[str] = None,
    min_proteins: Optional[float] = None,
    max_proteins: Optional[float] = None,
    min_carbs: Optional[float] = None,
    max_carbs: Optional[float] = None,
    min_fats: Optional[float] = None,
    max_fats: Optional[float] = None,
    min_calories: Optional[float] = None,
    max_calories: Optional[float] = None,
    limit: int = 10,
    skip: int = 0
) -> JSONResponse:
    """
    Mock function for get_recipe endpoint that returns saved response if available
    
    Args:
        request (Request): FastAPI request object
        lang (Optional[str]): Language filter
        difficulty (Optional[str]): Difficulty filter
        ingredients (Optional[str]): Ingredients filter
        diet_type (Optional[str]): Diet type filter
        max_prep_time (Optional[str]): Maximum preparation time
        min_proteins (Optional[float]): Minimum proteins
        max_proteins (Optional[float]): Maximum proteins
        min_carbs (Optional[float]): Minimum carbs
        max_carbs (Optional[float]): Maximum carbs
        min_fats (Optional[float]): Minimum fats
        max_fats (Optional[float]): Maximum fats
        min_calories (Optional[float]): Minimum calories
        max_calories (Optional[float]): Maximum calories
        limit (int): Number of results to return
        skip (int): Number of results to skip
        
    Returns:
        JSONResponse: The saved recipe response if available, otherwise empty list
    """
    if os.path.exists(MOCK_RECIPE_FILE):
        with open(MOCK_RECIPE_FILE, 'r', encoding='utf-8') as f:
            saved_response = json.load(f)
        return JSONResponse(content=saved_response)
    return JSONResponse(content=[])

async def mock_find_ingredient(
    query: str,
    lang: str,
    request: Request = None
) -> JSONResponse:
    """
    Mock function for find_ingredient endpoint that returns saved response if available
    
    Args:
        query (str): The search query
        lang (str): The language code
        request (Request): FastAPI request object
        
    Returns:
        JSONResponse: The saved ingredient response if available, otherwise empty results
    """
    if os.path.exists(MOCK_INGREDIENT_FILE):
        with open(MOCK_INGREDIENT_FILE, 'r', encoding='utf-8') as f:
            saved_response = json.load(f)
        return JSONResponse(content=saved_response)
    return JSONResponse(content={"results": []})

async def mock_analyze_refrigerator(
    file: UploadFile = File(..., description="The image file to analyze"),
    request: Request = None
) -> JSONResponse:
    """
    Mock function for analyze_refrigerator endpoint that returns saved response if available
    
    Args:
        file (UploadFile): The image file to analyze
        request (Request): FastAPI request object
        
    Returns:
        JSONResponse: The saved refrigerator analysis response if available, otherwise empty response
    """
    if os.path.exists(MOCK_FRIDGE_FILE):
        with open(MOCK_FRIDGE_FILE, 'r', encoding='utf-8') as f:
            saved_response = json.load(f)
        return JSONResponse(content=saved_response)
    return JSONResponse(content={
        "ingredients": [],
        "total_items": 0,
        "refrigerator_status": "empty",
        "recommendations": []
    })

async def mock_get_uploaded_file(filename: str) -> FileResponse:
    """
    Mock function for uploads endpoint that returns the requested file if available
    
    Args:
        filename (str): The name of the file to retrieve
        
    Returns:
        FileResponse: The requested file if available
        
    Raises:
        HTTPException: If the file is not found
    """
    file_path = os.path.join(MOCK_UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path) 