import logging
import os
import time
import asyncio
from typing import Optional, List, Dict, Any, Union
import json
from datetime import datetime
import pandas as pd

import httpx
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.responses import FileResponse

from backend.app_recipe.consts import RECIPE_FOLDER_APP
from backend.app_recipe.utils.ingredient_utils import get_ingredients_dataframe
from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client

OPENROUTER_API_KEY = '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'
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

# Cache for ingredients DataFrame
_ingredients_df_cache = None
name_to_english_cache = None  # Cache for the name-to-english mapping

def clean_document(doc):
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, dict):
            clean_document(value)
    return doc

def get_cached_ingredients_dataframe():
    """Get ingredients DataFrame from cache or fetch if not cached"""
    global _ingredients_df_cache
    if _ingredients_df_cache is None:
        _ingredients_df_cache = get_ingredients_dataframe()
    return _ingredients_df_cache

def generate_name_to_english_mapping(df):
    mapping = {}
    lang_columns = ['english_name', 'russian_name', 'spanish_name', 'hebrew_name']
    for _, row in df.iterrows():
        english = str(row['english_name']) if pd.notnull(row['english_name']) else ''
        for col in lang_columns:
            val = row[col]
            if pd.notnull(val) and str(val).strip():
                mapping[str(val).strip()] = english
    return mapping

async def translate_json_values(json_data: Union[dict, list]) -> Union[dict, list]:
    """
    Helper function to translate JSON values to Hebrew using OpenRouter.
    Returns the translated JSON with the same structure.
    Can handle both single dictionaries and lists of dictionaries.
    """
    try:
        # Handle empty results
        if not json_data:
            return json_data

        # Log the input data for debugging
        logger.info(f"Input JSON data: {json.dumps(json_data, ensure_ascii=False)}")

        # Prepare the translation prompt
        prompt = """Translate the following JSON values to Hebrew. Keep the keys in English and only translate the values.
        Return the response as a valid JSON object with the same structure.
        Important rules:
        1. Only translate values, not keys
        2. Keep numbers and special characters as is
        3. Maintain the same data types (arrays stay as arrays, objects stay as objects)
        4. Use proper Hebrew grammar and natural language
        5. Keep any HTML tags or special formatting intact
        6. If the input is a list of objects, maintain the list structure
        7. IMPORTANT: Your response must be valid JSON - do not include any explanatory text before or after the JSON
        8. Do not translate any numeric values or units (e.g., "5g", "100kcal")
        9. Keep all special characters and formatting exactly as they appear
        10. If a value is already in Hebrew, leave it unchanged
        
        Example input (single object):
        {
            "name": "John",
            "description": "A tall man",
            "items": ["apple", "banana"],
            "count": 5,
            "html": "<p>Hello</p>",
            "nutrition": "5g protein, 100kcal"
        }
        Example output (single object):
        {
            "name": "יוחנן",
            "description": "איש גבוה",
            "items": ["תפוח", "בננה"],
            "count": 5,
            "html": "<p>שלום</p>",
            "nutrition": "5g protein, 100kcal"
        }
        
        Example input (list of objects):
        [
            {
                "name": "John",
                "description": "A tall man"
            },
            {
                "name": "Mary",
                "description": "A short woman"
            }
        ]
        Example output (list of objects):
        [
            {
                "name": "יוחנן",
                "description": "איש גבוה"
            },
            {
                "name": "מרים",
                "description": "אישה נמוכה"
            }
        ]
        
        Here is the JSON to translate:
        """

        # Add the input JSON to the prompt
        prompt += json.dumps(json_data, ensure_ascii=False, indent=2)

        # Prepare the API request
        api_body = {
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "max_tokens": 4000  # Increase max tokens to handle larger responses
        }

        # Log the API request for debugging
        logger.info(f"API request body: {json.dumps(api_body, ensure_ascii=False)}")

        # Make the API call with retries
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://yourdomain.com",
                            "X-Title": "JSONTranslator"
                        },
                        json=api_body,
                        timeout=60.0
                    )

                    # Log the raw response for debugging
                    logger.info(f"API response status: {response.status_code}")
                    logger.info(f"API response headers: {dict(response.headers)}")
                    logger.info(f"API response body: {response.text}")

                    if response.status_code == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(f"Rate limited, retrying in {wait_time} seconds...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise HTTPException(status_code=429, detail="חריגת מכסה של בקשות. אנא נסה שוב מאוחר יותר.")

                    if response.status_code != 200:
                        error_detail = f"שגיאת API: {response.status_code} - {response.text}"
                        logger.error(error_detail)
                        raise HTTPException(status_code=500, detail=error_detail)

                    response_data = response.json()

                    # Check if we got a valid response structure
                    if not response_data.get("choices") or not response_data["choices"][0].get("message"):
                        error_msg = f"תגובת API לא תקינה: {json.dumps(response_data, ensure_ascii=False)}"
                        logger.error(error_msg)
                        raise HTTPException(status_code=500, detail=error_msg)

                    result = response_data["choices"][0]["message"]["content"]

                    # Log the raw response for debugging
                    logger.info(f"Raw translation response: {result}")

                    if not result or not result.strip():
                        error_msg = "התקבלה תגובה ריקה מהמודל"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            logger.warning(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            continue
                        raise HTTPException(status_code=500, detail=error_msg)

                    # Parse the JSON response
                    try:
                        # Try to clean the response if it contains any non-JSON text
                        result = result.strip()
                        if result.startswith("```json"):
                            result = result[7:]
                        if result.endswith("```"):
                            result = result[:-3]
                        result = result.strip()

                        translated_data = json.loads(result)

                        # Validate the structure matches the input
                        if isinstance(json_data, list) and not isinstance(translated_data, list):
                            raise ValueError("Expected list in response but got object")
                        elif isinstance(json_data, dict) and not isinstance(translated_data, dict):
                            raise ValueError("Expected object in response but got list")

                        # Validate that all keys from input exist in output
                        if isinstance(json_data, dict):
                            missing_keys = set(json_data.keys()) - set(translated_data.keys())
                            if missing_keys:
                                raise ValueError(f"Missing keys in translation: {missing_keys}")
                        elif isinstance(json_data, list):
                            if len(json_data) != len(translated_data):
                                raise ValueError(
                                    f"Length mismatch: input has {len(json_data)} items, output has {len(translated_data)} items")

                        return translated_data
                    except json.JSONDecodeError as e:
                        error_msg = f"שגיאה בפענוח התרגום: {str(e)}\nתוכן התגובה: {result}"
                        logger.error(error_msg)
                        if attempt < max_retries - 1:
                            logger.warning(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            continue
                        raise HTTPException(status_code=500, detail=error_msg)

            except httpx.RequestError as e:
                error_msg = f"שגיאת חיבור ל-API: {str(e)}"
                logger.error(error_msg)
                if attempt < max_retries - 1:
                    logger.warning(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    continue
                raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        error_msg = f"שגיאה בתרגום JSON: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/get_recipe")
async def get_recipe(
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
):
    try:
        client = get_mongo_client()
        db = client["recipe_db_v4"]
        pipeline = []

        if difficulty:
            difficulty_arr = [d.strip() for d in difficulty.split(",")]
            pipeline.append({
                "$match": {
                    "difficulty": {"$in": difficulty_arr}
                }
            })

        if ingredients:
            ingredient_list = [i.strip() for i in ingredients.split(",")]
            regex_conditions = [
                {"ingredients": {"$elemMatch": {"$regex": word, "$options": "i"}}}
                for word in ingredient_list
            ]
            pipeline.append({
                "$match": {
                    "$and": regex_conditions
                }
            })

        # Diet type
        if diet_type:
            pipeline.append({
                "$match": {
                    "suitable_diets": diet_type
                }
            })

        # Ensure all nutritional fields are valid format
        pipeline.append({
            "$match": {
                "total_proteins": {"$regex": r"^\d+(\.\d+)?g$"},
                "total_carbohydrates": {"$regex": r"^\d+(\.\d+)?g$"},
                "total_fats": {"$regex": r"^\d+(\.\d+)?g$"},
                "total_calories": {"$regex": r"^\d+(\.\d+)?kcal$"}
            }
        })

        # Build dynamic numeric conditions
        expr_conditions = []

        # Filter by total_time = prep_time + cook_time
        if max_prep_time is not None:
            total_time_limit = 0

            if max_prep_time is not None:
                total_time_limit += int(max_prep_time)

            pipeline.append({
                "$match": {
                    "$expr": {
                        "$lte": [
                            {
                                "$add": [
                                    {
                                        "$toInt": {
                                            "$trim": {
                                                "input": {
                                                    "$arrayElemAt": [
                                                        {"$split": ["$prep_time", " "]},
                                                        0
                                                    ]
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "$toInt": {
                                            "$trim": {
                                                "input": {
                                                    "$arrayElemAt": [
                                                        {"$split": ["$cook_time", " "]},
                                                        0
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                ]
                            },
                            total_time_limit
                        ]
                    }
                }
            })

        def build_expr(field: str, unit_char: str, min_val: Optional[float], max_val: Optional[float]):
            if min_val is not None:
                expr_conditions.append({
                    "$gte": [
                        {
                            "$convert": {
                                "input": {
                                    "$substrBytes": [f"${field}", 0, {"$indexOfBytes": [f"${field}", unit_char]}] 
                                },
                                "to": "double",
                                "onError": None
                            }
                        },
                        min_val
                    ]
                })
            if max_val is not None:
                expr_conditions.append({
                    "$lte": [
                        {
                            "$convert": {
                                "input": {
                                    "$substrBytes": [f"${field}", 0, {"$indexOfBytes": [f"${field}", unit_char]}]
                                },
                                "to": "double",
                                "onError": None
                            }
                        },
                        max_val
                    ]
                })

        # Build dynamic numeric conditions
        expr_conditions = []

        if min_proteins is not None or max_proteins is not None:
            build_expr("total_proteins", "g", min_proteins, max_proteins)

        if min_carbs is not None or max_carbs is not None:
            build_expr("total_carbohydrates", "g", min_carbs, max_carbs)

        if min_fats is not None or max_fats is not None:
            build_expr("total_fats", "g", min_fats, max_fats)

        if min_calories is not None or max_calories is not None:
            build_expr("total_calories", "k", min_calories, max_calories)

        # Add $expr only if there are actual conditions
        if expr_conditions:
            pipeline.append({
                "$match": {
                    "$expr": {
                        "$and": expr_conditions
                    }
                }
            })

        # Pagination
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        # Run query
        results = list(db.gpt_recipes.aggregate(pipeline))
        for r in results:
            r["_id"] = str(r["_id"])  # convert ObjectId to str

        try:
            # Convert to JSON-serializable format
            json_results = jsonable_encoder(results)

            if (lang == "he"):
                # Translate the results
                # translated_json = await translate_json_values(json_results[:2])
                # return JSONResponse(content=translated_json)
                return JSONResponse(content=json_results)
            else:
                return JSONResponse(content=json_results)

        except Exception as e:
            logger.error(f"Error translating recipe results: {str(e)}")
            # Return untranslated results if translation fails
            return JSONResponse(content=jsonable_encoder(results))

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error searching recipes: {str(e)}"}
        )

@router.get("/find_ingredient")
async def find_ingredient(
        query: str,
        lang: str,
        request: Request = None
):
    try:
        # Log the incoming request
        logger.info(f"Finding ingredient for query: {query} in language: {lang}")

        # Get the DataFrame from cache
        df = get_cached_ingredients_dataframe()

        # Generate and cache the name-to-english mapping if not already cached
        global name_to_english_cache
        if name_to_english_cache is None:
            name_to_english_cache = generate_name_to_english_mapping(df)
        name_to_english = name_to_english_cache

        # Define language column mappings
        lang_columns = {
            'en': ['primary_name', 'english_name', 'english_synonyms'],
            'ru': ['primary_name', 'russian_name', 'russian_synonyms'],
            'es': ['primary_name', 'spanish_name', 'spanish_synonyms'],
            'he': ['primary_name', 'hebrew_name', 'hebrew_synonyms']
        }

        # Define language name columns for deduplication
        lang_name_columns = {
            'en': 'english_name',
            'ru': 'russian_name',
            'es': 'spanish_name',
            'he': 'hebrew_name'
        }

        # Validate language
        if lang not in lang_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {lang}. Supported languages are: {', '.join(lang_columns.keys())}"
            )

        # Get columns to search for the given language
        search_columns = lang_columns[lang]

        # Create a mask for each column
        masks = []
        for col in search_columns:
            if col.endswith('_synonyms'):
                # For synonym columns, check if query is in the list
                mask = df[col].apply(
                    lambda x: query.lower() in [s.lower() for s in x] if isinstance(x, list) else False)
            else:
                # For name columns, do direct string comparison
                mask = df[col].str.lower().str.contains(query.lower(), na=False)
            masks.append(mask)

        # Combine masks with OR operation
        final_mask = masks[0]
        for mask in masks[1:]:
            final_mask = final_mask | mask

        # Filter the DataFrame
        filtered_df = df[final_mask]

        # Drop duplicates based on the selected language's name column
        name_column = lang_name_columns[lang]
        filtered_df = filtered_df.drop_duplicates(subset=[name_column])[
            ['primary_name', 'category_name', 'english_name', 'russian_name', 'spanish_name', 'hebrew_name',
             'proteins_per_100g', 'carbohydrates_per_100g', 'fats_per_100g', 'calories_per_100g']]
        filtered_df.dropna(inplace=True)
        # Add a column for sorting priority
        filtered_df['match_type'] = filtered_df[name_column].apply(
            lambda x: 0 if x.lower() == query.lower() else 1
        )

        # Sort by match type (exact matches first) and then by the name column
        filtered_df = filtered_df.sort_values(['match_type', name_column])

        # Remove the temporary sorting column
        filtered_df = filtered_df.drop('match_type', axis=1)

        # Convert all columns to string type
        for column in filtered_df.columns:
            filtered_df[column] = filtered_df[column].astype(str)

        # Convert to list of dictionaries
        results = filtered_df.to_dict('records')

        return JSONResponse(content={"results": results})

    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error finding ingredient: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/analyze_refrigerator")
async def analyze_refrigerator(
        file: UploadFile = File(..., description="The image file to analyze"),
        request: Request = None
):
    try:
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

        # Prepare the image URL
        image_url = f"https://{MY_SERVER_NAME}/recipe/uploads/{filename}"
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


@router.get("/uploads/{filename}")
async def uploaded_file(filename: str):
    file_path = os.path.join(RECIPE_FOLDER_APP, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
