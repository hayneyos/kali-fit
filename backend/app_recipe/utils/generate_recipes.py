import base64
import io
import os
import json
from typing import List, Dict, Tuple
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
import asyncio
import requests
import time

from backend.app_recipe.utils.base.mongo_client import recipes_collection, ingredient_names_collection, \
    ingredient_categories_collection, gpt_recipes_collection
from backend.app_recipe.utils.mongo_handler_utils import *

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_API_KEY = "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"
OPENROUTER_API_KEY = "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"

# BASE_MODEL_NAME = 'openai/gpt-4o'
# BASE_MODEL_NAME = 'openai/gpt-4o-mini' #'meta-llama/llama-4-maverick:free'
BASE_MODEL_NAME = 'google/gemini-2.5-flash-preview'  # 'meta-llama/llama-4-maverick:free'
MODEL_NAMES = ['openai/gpt-4o-mini', 'meta-llama/llama-4-maverick:free']
FINAL_MODEL = 'openai/gpt-4o'


def save_recipe_to_mongodb(recipe):
    """
    Save a recipe to the gpt_recipes collection and extract ingredient nutrition data
    with flattened structure
    """
    try:
        # Flatten the recipe data
        flattened_recipe = {
            'name': recipe.get('name'),
            'ingredients': recipe.get('ingredients', []),
            'instructions': recipe.get('instructions', []),
            'allergens': recipe.get('allergens', []),
            'allergen_free': recipe.get('allergen_free', []),
            'prep_time': recipe.get('prep_time'),
            'cook_time': recipe.get('cook_time'),
            'difficulty': recipe.get('difficulty'),
            'servings': recipe.get('servings'),
            'created_at': datetime.utcnow(),
            'source_model': recipe.get('source_model'),
            'input_ingredients': recipe.get('input_ingredients', []),
            'macronutrients_by_ingredient' : recipe.get('macronutrients_by_ingredient')
        }

        # Add macronutrients
        if 'macronutrients' in recipe:
            macronutrients = recipe['macronutrients']
            flattened_recipe.update({
                'total_proteins': macronutrients.get('proteins', '0g'),
                'total_carbohydrates': macronutrients.get('carbohydrates', '0g'),
                'total_fats': macronutrients.get('fats', '0g'),
                'total_calories': macronutrients.get('calories', '0kcal')
            })

        # Add per 100g macronutrients
        if 'macronutrients_per_100g' in recipe:
            per_100g = recipe['macronutrients_per_100g']
            flattened_recipe.update({
                'proteins_per_100g': per_100g.get('proteins', '0g'),
                'carbohydrates_per_100g': per_100g.get('carbohydrates', '0g'),
                'fats_per_100g': per_100g.get('fats', '0g'),
                'calories_per_100g': per_100g.get('calories', '0kcal')
            })

        # Add health recommendations
        if 'health_recommendations' in recipe:
            health = recipe['health_recommendations']

            flattened_recipe['name'] = recipe.get('name')
            flattened_recipe['original_recipe_name'] = recipe.get('original_recipe_name')
            flattened_recipe['cusine'] = recipe.get('cusine')
            flattened_recipe['course'] = recipe.get('course')

            flattened_recipe.update({
                'health_benefits': health.get('benefits', []),
                'health_considerations': health.get('considerations', []),
                'suitable_diets': health.get('suitable_for', []),
                'unsuitable_diets': health.get('not_suitable_for', [])
            })

        try:
            # Save the flattened recipe
            recipe_id = gpt_recipes_collection.insert_one(flattened_recipe).inserted_id
        except Exception as exp:
            print(exp)

        # Extract and save ingredient data
        if 'macronutrients_by_ingredient' in recipe:
            for ingredient_name, nutrition_data in recipe['macronutrients_by_ingredient'].items():
                try:
                    # First, handle the category
                    category_name = nutrition_data.get('category', 'Uncategorized')
                    category_doc = {
                        'name': category_name,
                        'created_at': datetime.utcnow()
                    }
                    category_result = ingredient_categories_collection.update_one(
                        {'name': category_name},
                        {'$setOnInsert': category_doc},
                        upsert=True
                    )
                    category_id = category_result.upserted_id or ingredient_categories_collection.find_one({'name': category_name})['_id']

                    # Handle ingredient names and synonyms
                    names_doc = {
                        'primary_name': ingredient_name,
                        'category_id': category_id,
                        'names': {
                            'english': {
                                'name': ingredient_name,
                                'synonyms': nutrition_data.get('names', {}).get('english', {}).get('synonyms', [])
                            },
                            'russian': {
                                'name': nutrition_data.get('names', {}).get('russian', {}).get('name', ''),
                                'synonyms': nutrition_data.get('names', {}).get('russian', {}).get('synonyms', [])
                            },
                            'spanish': {
                                'name': nutrition_data.get('names', {}).get('spanish', {}).get('name', ''),
                                'synonyms': nutrition_data.get('names', {}).get('spanish', {}).get('synonyms', [])
                            },
                            'hebrew': {
                                'name': nutrition_data.get('names', {}).get('hebrew', {}).get('name', ''),
                                'synonyms': nutrition_data.get('names', {}).get('hebrew', {}).get('synonyms', [])
                            }
                        },
                        'created_at': datetime.utcnow(),
                        'last_updated': datetime.utcnow()
                    }
                    names_result = ingredient_names_collection.update_one(
                        {'primary_name': ingredient_name},
                        {'$set': names_doc},
                        upsert=True
                    )
                    names_id = names_result.upserted_id or ingredient_names_collection.find_one({'primary_name': ingredient_name})['_id']

                    # Create a flattened document for the ingredient nutrition
                    nutrition_doc = {
                        'ingredient_names_id': names_id,
                        'category_id': category_id,
                        'weight': nutrition_data.get('weight', '0g'),
                        'proteins': nutrition_data.get('proteins', '0g'),
                        'carbohydrates': nutrition_data.get('carbohydrates', '0g'),
                        'fats': nutrition_data.get('fats', '0g'),
                        'calories': nutrition_data.get('calories', '0kcal'),
                        'proteins_per_100g': nutrition_data.get('proteins_per_100g', '0g'),
                        'carbohydrates_per_100g': nutrition_data.get('carbohydrates_per_100g', '0g'),
                        'fats_per_100g': nutrition_data.get('fats_per_100g', '0g'),
                        'calories_per_100g': nutrition_data.get('calories_per_100g', '0kcal'),
                        'source_recipe_id': recipe_id,
                        'last_updated': datetime.utcnow()
                    }

                    # Update or insert the ingredient nutrition data
                    ingredients_nutrition_collection.update_one(
                        {'ingredient_names_id': names_id},
                        {'$set': nutrition_doc},
                        upsert=True
                    )
                except Exception as exp:
                    print(f"Error processing ingredient {ingredient_name}: {str(exp)}")

        return recipe_id
    except Exception as e:
        print(f"Error saving recipe to MongoDB: {str(e)}")
        return None

async def update_recipe(model: str, recipe: Dict) -> List[Dict]:
    """
    Generate a new recipe variation based on an existing recipe.
    
    Args:
        model (str): The model to use for recipe generation
        recipe (Dict): The original recipe to base the variation on
        
    Returns:
        List[Dict]: List of generated recipe variations
    """
    try:
        # Extract key information from the original recipe
        recipe_info = {
            'name': recipe.get('title', ''),
            'ingredients': recipe.get('ingredients', []),
            'instructions': recipe.get('directions', []),
            'source': recipe.get('source',''),
            'tags': recipe.get('tags', ''),
            'url': recipe.get('url', ''),
        }

        # Build the prompt with proper string formatting
        base_prompt = f"""Given these recipes: {recipe_info}
                        Complete the data and return a new recipe based on the following structure:                        
                        For each recipe, provide:
                        Return the new recipe in the following structure:
                        {{
                            "name": "New recipe name",
                            "ingredients": ["List of ingredients"],
                            "instructions": ["Step by step instructions"],
                            "prep_time": "Preparation time in minutes",
                            "cook_time": "Cooking time in minutes",
                            "difficulty": "One of [Easy, Medium, Hard]",
                            "servings": "Number of servings",
                            "cusine": "ex: Amirican / Asian / French",
                            "course": "One of [Breakfast, Lunch, Dinner, Snack, Any]",
                            "macronutrients": {{
                                "proteins": "Xg",
                                "carbohydrates": "Xg",
                                "fats": "Xg",
                                "calories": "Xkcal"
                            }},
                            "macronutrients_by_ingredient": {{
                                "ingredient_name": {{
                                    "category": "e.g., Vegetables/Fruits/Eggs/Fat And Oils/Grains/Legumes/Dairy/Meat/Fish/Other",
                                    "names": {{
                                        "english": {{
                                            "name": "english name",
                                            "synonyms": ["english synonym 1", "english synonym 2"]
                                        }},
                                        "russian": {{
                                            "name": "russian name",
                                            "synonyms": ["russian synonym 1", "russian synonym 2"]
                                        }},
                                        "spanish": {{
                                            "name": "spanish name",
                                            "synonyms": ["spanish synonym 1", "spanish synonym 2"]
                                        }},
                                        "hebrew": {{
                                            "name": "hebrew name",
                                            "synonyms": ["hebrew synonym 1", "hebrew synonym 2"]
                                        }}
                                    }},
                                    "weight": "Xg or Xml",
                                    "proteins": "Xg",
                                    "carbohydrates": "Xg",
                                    "fats": "Xg",
                                    "calories": "Xkcal",
                                    "proteins_per_100g": "Xg",
                                    "carbohydrates_per_100g": "Xg",
                                    "fats_per_100g": "Xg",
                                    "calories_per_100g": "Xkcal"
                                }}
                            }},
                            "macronutrients_per_100g": {{
                                "proteins": "Xg",
                                "carbohydrates": "Xg",
                                "fats": "Xg",
                                "calories": "Xkcal"
                            }},
                            "health_recommendations": {{
                                "benefits": ["List of health benefits"],
                                "considerations": ["List of health considerations or warnings"],
                                "suitable_for": [
                                   "List of dietary types or health conditions this recipe is suitable for, e.g., vegan, vegetarian, keto, paleo, kosher, halal, gluten-free, dairy-free, low-carb, diabetic-friendly, heart-healthy, weight loss, anti-inflammatory, low-sodium"
                                ],
                                "not_suitable_for": [
                                   "List of dietary types or health conditions this recipe is not suitable for, e.g., not kosher, not vegetarian, not gluten-free, not halal, contains pork, high cholesterol, hypertension, diabetes, IBS, kidney disease"
                                ]
                            }},
                            "allergens": ["List of potential allergens"],
                            "allergen_free": ["List of allergens this recipe is free from"]
                        }}
                        
                        Return the response as a JSON object."""

        model = "google/gemini-2.5-flash-preview"
        # model = "deepseek/deepseek-prover-v2:free"
        # Prepare the API request
        body = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": base_prompt
                        },
                    ]
                }
            ],
            "temperature": 0,  # Increased for more variation
            "response_format": {"type": "json_object"}
        }

        # Make the API call
        openrouter_response = await execute_call(body, model)

        if not openrouter_response or not hasattr(openrouter_response, 'json'):
            print("Error: Invalid response from API")
            return []

        try:
            response_json = openrouter_response.json()
            message_content = response_json["choices"][0]["message"]["content"]

            # Convert the JSON string inside "content" to a Python dict
            new_recipe = json.loads(message_content)

            # Add metadata
            new_recipe['created_at'] = datetime.utcnow()
            new_recipe['source_model'] = model
            new_recipe['original_recipe_id'] = recipe.get('_id')
            if (new_recipe['name']!=recipe_info['name']):
                new_recipe['original_recipe_name'] = recipe_info['name']

            # Save to MongoDB
            recipe_id = save_recipe_to_mongodb(new_recipe)
            if recipe_id:
                new_recipe['_id'] = recipe_id
                
                # Print recipe details
                print(f"\nGenerated new recipe variation:")
                print(f"Name: {new_recipe.get('name', 'N/A')}")
                print(f"Course: {new_recipe.get('course', 'Any')}")
                print(f"Ingredients: {', '.join(new_recipe.get('ingredients', []))}")
                print(f"Prep Time: {new_recipe.get('prep_time', 'N/A')} mins")
                print(f"Cook Time: {new_recipe.get('cook_time', 'N/A')} mins")
                print(f"Difficulty: {new_recipe.get('difficulty', 'N/A')}")
                print(f"Servings: {new_recipe.get('servings', 'N/A')}")
                if 'macronutrients' in new_recipe:
                    print(f"Calories: {new_recipe['macronutrients'].get('calories', 'N/A')}")
                print("\nInstructions:")
                for step in new_recipe.get('instructions', []):
                    print(f"- {step}")
                print("-" * 80)
                
                return [new_recipe]
            else:
                print("Failed to save new recipe to database")
                return []

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {str(e)}")
            print(f"Raw response content: {message_content}")
            return []
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            return []

    except Exception as e:
        print(f"Error in update_recipe: {str(e)}")
        return []


async def process_recipe(recipe: Dict, model: str = "anthropic/claude-3-opus-20240229") -> bool:
    """
    Process a single recipe to generate new variations.
    
    Args:
        recipe (Dict): The recipe to process
        model (str): The model to use for generation
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"\nProcessing recipe: {recipe.get('name', 'Unknown')}")
        print(f"Course: {recipe.get('course', 'Any')}")
        print(f"Ingredients: {', '.join(recipe.get('ingredients', []))}")

        # Generate new recipe variation
        new_recipes = await update_recipe(model=model, recipe=recipe)

        if new_recipes:
            print(f"Generated {len(new_recipes)} new recipe variations")
            return True
        else:
            print("No new recipes generated")
            return False

    except Exception as e:
        print(f"Error processing recipe: {str(e)}")
        return False


async def check_recipe_exists(title: str) -> bool:
    """
    Check if a recipe with the given title already exists in the database.
    
    Args:
        title (str): The recipe title to check
        
    Returns:
        bool: True if recipe exists, False otherwise
    """
    try:
        existing_recipe = gpt_recipes_collection.find_one({'name': title})
        return existing_recipe is not None
    except Exception as e:
        print(f"Error checking recipe existence: {str(e)}")
        return False

async def process_recipe_batch(recipes: List[Dict], model: str) -> Tuple[int, int]:
    """
    Process a batch of recipes in parallel, skipping those that already exist.
    
    Args:
        recipes (List[Dict]): List of recipes to process
        model (str): The model to use for generation
        
    Returns:
        Tuple[int, int]: Number of processed and successful recipes
    """
    tasks = []
    for recipe in recipes:
        # Check if recipe already exists by title
        if await check_recipe_exists(recipe.get('title', '')):
            print(f"Skipping existing recipe: {recipe.get('title', 'Unknown')}")
            continue
            
        task = asyncio.create_task(process_recipe(recipe, model))
        tasks.append(task)
    
    if not tasks:
        print("No new recipes to process in this batch")
        return 0, 0
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    processed = len(tasks)
    successful = sum(1 for result in results if result is True)
    
    return processed, successful

async def generate_recipe_variations(batch_size: int = 10, model: str = "deepseek/deepseek-prover-v2:free", max_concurrent: int = 10):
    """
    Generate variations of existing recipes using parallel processing.
    
    Args:
        batch_size (int): Number of recipes to process in each batch
        model (str): The model to use for generation
        max_concurrent (int): Maximum number of concurrent tasks
    """
    try:
        # Get total count of recipes
        total_recipes = recipes_collection.count_documents({})
        print(f"Found {total_recipes} recipes in database")

        # Process recipes in batches
        processed = 0
        successful = 0
        skipped = 0
        batch_number = 1

        while processed < total_recipes:
            # Get batch of recipes
            cursor = recipes_collection.find({}).skip(processed).limit(batch_size)
            recipes = list(cursor)

            if not recipes:
                break

            print(f"\nProcessing batch {batch_number} ({len(recipes)} recipes)")

            # Process the batch
            batch_processed, batch_successful = await process_recipe_batch(recipes, model)
            
            # Always increment processed by the batch size, even if recipes were skipped
            processed += len(recipes)
            successful += batch_successful
            skipped += len(recipes) - batch_processed

            print(f"\nProgress: {processed}/{total_recipes} recipes processed")
            print(f"Successfully generated variations for {successful} recipes")
            print(f"Skipped {skipped} existing recipes")
            
            # Calculate success rate only if we've processed any recipes
            if processed > 0:
                success_rate = (successful/processed)*100
                print(f"Current success rate: {success_rate:.2f}%")
            else:
                print("No recipes processed yet")

            # Add a small delay between batches to avoid rate limits
            await asyncio.sleep(2)
            batch_number += 1

            # Print a summary every 1000 recipes
            if processed % 1000 == 0:
                print(f"\n=== Progress Summary at {processed} recipes ===")
                print(f"Total processed: {processed}/{total_recipes} ({(processed/total_recipes)*100:.2f}%)")
                print(f"Successfully generated: {successful}")
                print(f"Skipped: {skipped}")
                if processed > 0:
                    print(f"Success rate: {(successful/processed)*100:.2f}%")
                print("=" * 40)

        print("\nFinal Statistics:")
        print(f"Total recipes processed: {processed}")
        print(f"Successfully generated variations: {successful}")
        print(f"Skipped existing recipes: {skipped}")
        
        # Calculate final success rate only if we've processed any recipes
        if processed > 0:
            final_success_rate = (successful/processed)*100
            print(f"Overall success rate: {final_success_rate:.2f}%")
        else:
            print("No recipes were processed")

    except Exception as e:
        print(f"Error in generate_recipe_variations: {str(e)}")
    finally:
        print("MongoDB connection closed")

def _convert_to_serializable(value):
    """Convert non-JSON serializable values to strings or remove them"""
    try:
        if value is None:
            return None
        elif isinstance(value, (int, float, str, bool)):
            return value
        elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):  # Handle IFDRational
            return f"{value.numerator}/{value.denominator}"
        elif isinstance(value, (tuple, list)):
            return [_convert_to_serializable(item) for item in value]
        elif isinstance(value, dict):
            return {str(k): _convert_to_serializable(v) for k, v in value.items()}
        elif hasattr(value, '__dict__'):  # Handle objects with __dict__
            return _convert_to_serializable(value.__dict__)
        elif hasattr(value, 'isoformat'):  # Handle datetime objects
            return value.isoformat()
        elif hasattr(value, 'hex'):  # Handle bytes
            return value.hex()
        else:
            return str(value)
    except Exception as e:
        print(f"Warning: Could not convert value {value} to serializable format: {str(e)}")
        return str(value)


def process_single_image(image_data, is_base64=True):
    """Process a single image and return its details"""
    try:
        if is_base64:
            # Handle base64 image
            image_data = base64.b64decode(image_data.split(',')[1])
            source_type = 'base64'
        else:
            # Handle file path
            source_type = 'file'

        with Image.open(io.BytesIO(image_data) if is_base64 else image_data) as img:
            # Get basic image info
            basic_info = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': len(image_data) if is_base64 else os.path.getsize(image_data),
                'aspect_ratio': round(img.width / img.height, 3),
                'orientation': 'landscape' if img.width > img.height else 'portrait' if img.height > img.width else 'square',
                'source_type': source_type,
                'processing_time': time.time()  # Add timestamp for tracking
            }

            # Get other image info
            other_info = {}
            try:
                for key, value in img.info.items():
                    try:
                        other_info[key] = _convert_to_serializable(value)
                    except Exception as e:
                        print(f"Warning: Could not process image info {key}: {str(e)}")
                        continue
            except Exception as e:
                print(f"Warning: Could not process image info: {str(e)}")

            # Combine all info
            return _convert_to_serializable({
                **basic_info,
                'image_info': other_info
            })

    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def extract_image_details_from_body(body):
    """Extract image details from the request body"""
    image_details = {}
    try:
        # Find image URL in the body
        for message in body.get('messages', []):
            if isinstance(message.get('content'), list):
                for content in message['content']:
                    if content.get('type') == 'image_url':
                        image_url = content.get('image_url', {}).get('url', '')
                        if image_url.startswith('data:image'):
                            # Process base64 image
                            image_details = process_single_image(image_url, is_base64=True)
                        elif image_url.startswith('file://'):
                            # Process file image
                            file_path = image_url[7:]  # Remove 'file://'
                            image_details = process_single_image(file_path, is_base64=False)
                        else:
                            # Handle URL
                            image_details = {
                                'source_type': 'url',
                                'url': image_url
                            }
    except Exception as e:
        print(f"Error extracting image details from body: {str(e)}")

    return image_details

async def execute_call(body, model, file_name="", image_path="", version="v1", environment="prod", prompt_id=1):
    start_time = time.time()  # Start timing

    # Extract image details from body before API call
    image_details = extract_image_details_from_body(body)

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=body,
            timeout=60
        )

    except Exception as e:
        print(f"Error in API call: {str(e)}")
        response = {}

    return response
#
# if __name__ == "__main__":
#     # Run the async function with parallel processing
#     asyncio.run(generate_recipe_variations(batch_size=10, max_concurrent=10))
