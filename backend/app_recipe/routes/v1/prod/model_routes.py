import base64
import io
import json
import logging
import os
import time
import base64
from PIL import Image
import io
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, create_model
from datetime import datetime

import httpx
from functools import lru_cache
import asyncio

from backend.app_recipe.consts import UPLOAD_FOLDER_APP, MOCK_FOLDER, RECIPE_FOLDER_APP
from backend.app_recipe.services.wrapper_db.MyDbPostgresService import MyDbPostgresService
from backend.app_recipe.services.wrapper_db.WrapperService import count_requests_in_db
from backend.app_recipe.utils.generate_recipes import execute_call
from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.dish_db import DishDatabase
from backend.app_recipe.utils.model_common_util import OPENROUTER_API_KEY
from backend.app_recipe.utils.model_meals_util import get_openrouter_api_key, VALIDATION_MODEL_PROD, \
    create_openrouter_client_for_meals

# OPENROUTER_API_KEY = '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'
MY_SERVER_NAME = "for-checking.live"  # Your server domain
BASE_MODEL_NAME = 'google/gemini-2.5-flash-preview'  # 'meta-llama/llama-4-maverick:free'

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('recipe_routes')

# Load environment variables
router = APIRouter()
db_service = MyDbPostgresService()

@router.post("/predict_meals")
async def proxy_openai(request: Request, api_key: str = Depends(get_openrouter_api_key)):
    try:
        body = await request.json()
        email = body.get("email")
        device_id = body.get("device_id")
        image_name = body.get("image_name", "-")
        version = body.get("version", "-")
        ip_address = request.client.host

        email_count = await count_requests_in_db("email", email, logger)
        device_count = await count_requests_in_db("device_id", device_id, logger)
        ip_address_count = await count_requests_in_db("ip_address", ip_address, logger)

        # if not email is None and email_count >= 30:
        #     raise HTTPException(status_code=429, detail="Email rate limit exceeded")
        # if device_id and device_count >= 3 and email is None:
        #     raise HTTPException(status_code=429, detail="Device rate limit exceeded")
        # if ip_address_count >= 30:
        #     raise HTTPException(status_code=429, detail="IP rate limit exceeded")

        body['model'] = BASE_MODEL_NAME

        # Remove metadata fields from body
        for field in ["email", "device_id", "ip_address", "image_name", "version"]:
            body.pop(field, None)

        openrouter_response = {}
        try:
            start_time = time.time()
            db = DishDatabase()  # Initialize database
            prompt_id = db.get_or_create_prompt(VALIDATION_MODEL_PROD)

            openrouter_response = await create_openrouter_client_for_meals(body, image_name, version=version, environment="prod",
                                                      prompt_id=prompt_id)  # ✅ await the coroutine

            if hasattr(openrouter_response, 'json'):
                try:
                    response_json = openrouter_response.json()
                    message_content = response_json["choices"][0]["message"]["content"]

                    # Save response to JSON file in mock folder only if it doesn't exist
                    os.makedirs(MOCK_FOLDER, exist_ok=True)
                    response_file_path = os.path.join(MOCK_FOLDER, 'predict_meals.json')
                    
                    if not os.path.exists(response_file_path):
                        with open(response_file_path, 'w') as f:
                            json.dump(message_content, f, indent=2)
                        logger.info(f"Response saved to {response_file_path}")
                    else:
                        logger.info(f"File {response_file_path} already exists, skipping save")

                    # Convert the JSON string inside "content" to a Python dict
                    parsed_content = json.loads(message_content)

                    print(f"{body['model']} ---> {json.dumps(parsed_content, indent=2)}")  # Pretty print actual data

                except Exception as e:
                    print("❌ Failed to parse:", str(e))
                    print(f"Raw response: {body['model']}", openrouter_response.text)
            else:
                print("Invalid response object:", openrouter_response)

            end_time = time.time()
            logger.info(f"create_openrouter_client: {end_time - start_time:.4f} seconds")
            logger.info(str(openrouter_response))

            start_time = time.time()
            db_service.insert_openai_log(email, device_id, ip_address, body, openrouter_response.json())
            end_time = time.time()
            logger.info(f"Request {start_time:.2f} - DB logging completed in {end_time - start_time  :.4f} seconds")

            if email:
                start_time = time.time()
                db_service.create_users_table()
                db_service.upsert_user(email, device_id, ip_address)
                end_time = time.time()
                logger.info(
                    f"Request {start_time:.2f} - User operations completed in {end_time - start_time:.4f} seconds")

        except Exception as e:
            print('error')



        return JSONResponse(content=openrouter_response.json(), status_code=openrouter_response.status_code)

    except requests.RequestException as e:
        logger.error(f"OpenRouter API error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error contacting OpenRouter")


@router.post("/find_ingredient_by_image")
async def analyze_refrigerator(
        file: UploadFile = File(..., description="The image file to analyze"),
        request: Request = None
):
    try:
        print('yossi')
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fridge_{timestamp}_{file.filename}"

        # Create upload directory if it doesn't exist
        os.makedirs(RECIPE_FOLDER_APP, exist_ok=True)

        # Save the uploaded file
        file_location = os.path.join(RECIPE_FOLDER_APP, filename)
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
        # https://for-checking.live/api/uploads/fridge_20250608_093315_BANANA.jpg/recipe
        # Prepare the image URL
        image_url = f"https://{MY_SERVER_NAME}/api/uploads/{filename}/recipe"
        logger.info(f"Image saved and URL generated: {image_url}")

        model = BASE_MODEL_NAME

        PROMPT = """Analyze this image and identify all visible food items and ingredients.
        Return a JSON object with the following structure:
        {
            "ingredients": [
                {
                    "name": "string (name of the ingredient)",
                    "quantity": "string (estimated quantity)",
                    "confidence": number (0-100),
                    "location": "string (e.g., 'top shelf', 'door', 'drawer')",
                    "expiry_status": "string (e.g., 'fresh', 'expiring soon', 'expired')"
                }
            ],
            "total_items": number,
            "refrigerator_status": "string (e.g., 'well-stocked', 'needs restocking', 'empty')",
            "recommendations": ["string (list of recommendations)"]
        }
        """

        HEADERS = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yourdomain.com",
            "X-Title": "FridgeVisionAnalyzer"
        }

        # Make the API call
        async with httpx.AsyncClient() as client:
            body = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            }

            logger.info(f"Sending request to OpenRouter with body: {json.dumps(body, indent=2)}")

            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=HEADERS,
                json=body,
                timeout=60.0
            )

            if response.status_code != 200:
                error_detail = f"OpenRouter API error: {response.status_code} - {response.text}"
                logger.error(error_detail)
                raise HTTPException(status_code=500, detail=error_detail)

            response_data = response.json()
            logger.info(f"Received response from OpenRouter: {json.dumps(response_data, indent=2)}")

            result = response_data["choices"][0]["message"]["content"]

            # Parse the JSON response
            try:
                result_json = json.loads(result)

                # Save response to JSON file in mock folder only if it doesn't exist
                os.makedirs(MOCK_FOLDER, exist_ok=True)
                response_file_path = os.path.join(MOCK_FOLDER, 'find_ingredient_by_image.json')

                if not os.path.exists(response_file_path):
                    with open(response_file_path, 'w') as f:
                        json.dump(result_json, f, indent=2)
                    logger.info(f"Response saved to {response_file_path}")
                else:
                    logger.info(f"File {response_file_path} already exists, skipping save")


                return JSONResponse(content=result_json)
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse analysis result: {str(e)}"
                logger.error(error_msg)
                return JSONResponse(
                    status_code=500,
                    content={"error": error_msg, "raw_result": result}
                )

    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error analyzing refrigerator image: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

