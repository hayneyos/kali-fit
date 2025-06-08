import logging
import os
import asyncio
from typing import Optional, List, Dict, Any, Union
import json
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

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


def clean_document(doc):
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, dict):
            clean_document(value)
    return doc

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
