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
    ingredient_categories_collection, gpt_recipes_collection, ingredients_nutrition_collection
from backend.app_recipe.utils.mongo_handler_utils import *

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OPENROUTER_API_KEY = "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"
OPENROUTER_API_KEY = "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"

# BASE_MODEL_NAME = 'openai/gpt-4o'
# BASE_MODEL_NAME = 'openai/gpt-4o-mini' #'meta-llama/llama-4-maverick:free'
BASE_MODEL_NAME = 'google/gemini-2.5-flash-preview'  # 'meta-llama/llama-4-maverick:free'
MODEL_NAMES = ['openai/gpt-4o-mini', 'meta-llama/llama-4-maverick:free']
FINAL_MODEL = 'openai/gpt-4o'


def save_recipe_to_mongodb(recipe,recipe_info):
    """
    Save a recipe to the gpt_recipes collection and extract ingredient nutrition data
    with flattened structure
    """
    try:
        # Flatten the recipe data
        flattened_recipe = {
            'name': recipe.get('name'),
            'original_recipe_name':recipe_info['name'],
            'ingredients': recipe.get('ingredients', []),
            'base_ingredient_name': recipe.get('base_ingredient_name', []),
            'instructions': recipe.get('instructions', []),
            'allergens': recipe.get('allergens', []),
            'allergen_free': recipe.get('allergen_free', []),
            'prep_time': recipe.get('prep_time'),
            'cook_time': recipe.get('cook_time'),
            'difficulty': recipe.get('difficulty'),
            'servings': recipe.get('servings'),
            'cusine': recipe.get('cusine'),
            'course': recipe.get('course'),
            'created_at': datetime.utcnow(),
            'source_model': recipe.get('source_model'),
            'input_ingredients': recipe.get('input_ingredients', []),
            'macronutrients_by_ingredient' : recipe.get('macronutrients_by_ingredient'),
            'kosher':recipe.get('kosher'),
            'halal': recipe.get('halal'),
            'gluten_free': recipe.get('gluten_free'),
            'dairy_free': recipe.get('dairy_free'),
            'low_carb': recipe.get('low_carb'),
            'diabetic_friendly': recipe.get('diabetic_friendly'),
            'heart_healthy': recipe.get('heart_healthy'),
            'health_rank': recipe.get('health_rank'),
            'tasty_rank': recipe.get('tasty_rank'),

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

        if ('macronutrients_per_for_this_meal_100g' in recipe):
            base_name = 'macronutrients_per_for_this_meal_100g'
        else:
            base_name = 'macronutrients_per_100g'
        # Add per 100g macronutrients
        if base_name in recipe:
            per_100g = recipe[base_name]
            flattened_recipe.update({
                'proteins': per_100g.get('proteins', '0g'),
                'carbohydrates': per_100g.get('carbohydrates', '0g'),
                'fats': per_100g.get('fats', '0g'),
                'calories': per_100g.get('calories', '0kcal')
            })

        # Add health recommendations
        if 'health_recommendations' in recipe:
            health = recipe['health_recommendations']
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
                    possible_measurement = nutrition_data.get('possible_measurement', [])
                    base_ingredient_name = nutrition_data.get('base_ingredient_name', [])
                    average_weight = nutrition_data.get('average_weight', "")
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

                    # Create a flattened document for the ingredient nutrition first
                    nutrition_doc = {
                        'ingredient_name': ingredient_name,
                        'category_id': category_id,
                        'possible_measurement': possible_measurement,
                        'base_ingredient_name': base_ingredient_name,
                        'average_weight': average_weight,
                        'data_sources': [{
                            'source': nutrition_data.get('data_source', 'unknown'),
                            'proteins_per_100g': nutrition_data.get('proteins_per_100g', '0g'),
                            'carbohydrates_per_100g': nutrition_data.get('carbohydrates_per_100g', '0g'),
                            'fats_per_100g': nutrition_data.get('fats_per_100g', '0g'),
                            'calories_per_100g': nutrition_data.get('calories_per_100g', '0kcal'),
                            'last_updated': datetime.utcnow()
                        }],
                        'last_updated': datetime.utcnow()
                    }

                    # Validate nutritional values before saving
                    is_valid, error_message = validate_nutritional_values(
                        nutrition_doc['data_sources'][0],
                        category=nutrition_data.get('category')
                    )
                    if not is_valid:
                        print(f"Invalid nutritional values for {ingredient_name}: {error_message}")
                        continue

                    # Check if this data source already exists for this ingredient
                    existing_doc = ingredients_nutrition_collection.find_one({
                        'ingredient_name': ingredient_name,
                        'data_sources.source': nutrition_data.get('data_source', 'unknown')
                    })

                    if existing_doc:
                        # Update the existing data source if the new data is different
                        new_data = nutrition_doc['data_sources'][0]
                        existing_data = next(
                            (ds for ds in existing_doc['data_sources'] 
                             if ds['source'] == new_data['source']),
                            None
                        )
                        
                        if existing_data and (
                            existing_data['proteins_per_100g'] != new_data['proteins_per_100g'] or
                            existing_data['carbohydrates_per_100g'] != new_data['carbohydrates_per_100g'] or
                            existing_data['fats_per_100g'] != new_data['fats_per_100g'] or
                            existing_data['calories_per_100g'] != new_data['calories_per_100g']
                        ):
                            # Update the existing data source with new values
                            ingredients_nutrition_collection.update_one(
                                {
                                    'ingredient_name': ingredient_name,
                                    'data_sources.source': new_data['source']
                                },
                                {
                                    '$set': {
                                        'data_sources.$.proteins_per_100g': new_data['proteins_per_100g'],
                                        'data_sources.$.carbohydrates_per_100g': new_data['carbohydrates_per_100g'],
                                        'data_sources.$.fats_per_100g': new_data['fats_per_100g'],
                                        'data_sources.$.calories_per_100g': new_data['calories_per_100g'],
                                        'data_sources.$.last_updated': new_data['last_updated']
                                    }
                                }
                            )
                            nutrition_id = existing_doc['_id']
                    else:
                        # Insert new document with the data source
                        result = ingredients_nutrition_collection.update_one(
                            {'ingredient_name': ingredient_name},
                            {
                                '$setOnInsert': {
                                    'ingredient_name': ingredient_name,
                                    'category_id': category_id,
                                    'possible_measurement': possible_measurement,
                                    'base_ingredient_name': base_ingredient_name,
                                    'average_weight': average_weight,
                                    'last_updated': datetime.utcnow()
                                },
                                '$push': {'data_sources': nutrition_doc['data_sources'][0]}
                            },
                            upsert=True
                        )
                        # Get the nutrition_id after saving
                        nutrition_doc = ingredients_nutrition_collection.find_one({'ingredient_name': ingredient_name})
                        if not nutrition_doc:
                            print(f"Error: Failed to create nutrition document for {ingredient_name}")
                            continue
                        nutrition_id = nutrition_doc['_id']

                    # Handle ingredient names and synonyms
                    try:
                        names_doc = {
                            'primary_name': ingredient_name,
                            'category_id': category_id,
                            'nutrition_id': nutrition_id,  # Now we have the correct nutrition_id
                            'names': {
                                'english': {
                                    'singular': {
                                        'name': nutrition_data.get('names', {}).get('english', {}).get('name', {}).get('singular', ingredient_name),
                                        'synonyms': nutrition_data.get('names', {}).get('english', {}).get('synonyms', [])
                                    },
                                    'plural': {
                                        'name': nutrition_data.get('names', {}).get('english', {}).get('name', {}).get('plural', nutrition_data.get('names', {}).get('english', {}).get('name', {}).get('singular', ingredient_name)),
                                        'synonyms': nutrition_data.get('names', {}).get('english', {}).get('synonyms', [])
                                    }
                                },
                                'russian': {
                                    'singular': {
                                        'name': nutrition_data.get('names', {}).get('russian', {}).get('name', {}).get('singular', ''),
                                        'synonyms': nutrition_data.get('names', {}).get('russian', {}).get('synonyms', [])
                                    },
                                    'plural': {
                                        'name': nutrition_data.get('names', {}).get('russian', {}).get('name', {}).get('plural', nutrition_data.get('names', {}).get('russian', {}).get('name', {}).get('singular', '')),
                                        'synonyms': nutrition_data.get('names', {}).get('russian', {}).get('synonyms', [])
                                    }
                                },
                                'spanish': {
                                    'singular': {
                                        'name': nutrition_data.get('names', {}).get('spanish', {}).get('name', {}).get('singular', ''),
                                        'synonyms': nutrition_data.get('names', {}).get('spanish', {}).get('synonyms', [])
                                    },
                                    'plural': {
                                        'name': nutrition_data.get('names', {}).get('spanish', {}).get('name', {}).get('plural', nutrition_data.get('names', {}).get('spanish', {}).get('name', {}).get('singular', '')),
                                        'synonyms': nutrition_data.get('names', {}).get('spanish', {}).get('synonyms', [])
                                    }
                                },
                                'hebrew': {
                                    'singular': {
                                        'name': nutrition_data.get('names', {}).get('hebrew', {}).get('name', {}).get('singular', ''),
                                        'synonyms': nutrition_data.get('names', {}).get('hebrew', {}).get('synonyms', [])
                                    },
                                    'plural': {
                                        'name': nutrition_data.get('names', {}).get('hebrew', {}).get('name', {}).get('plural', nutrition_data.get('names', {}).get('hebrew', {}).get('name', {}).get('singular', '')),
                                        'synonyms': nutrition_data.get('names', {}).get('hebrew', {}).get('synonyms', [])
                                    }
                                }
                            },
                            'created_at': datetime.utcnow(),
                            'last_updated': datetime.utcnow()
                        }

                        # Create separate records for singular and plural forms
                        for lang in ['english', 'russian', 'spanish', 'hebrew']:
                            # Handle singular form
                            singular_name = names_doc['names'][lang]['singular']['name']
                            if singular_name:  # Only create record if singular name exists
                                singular_doc = {
                                    'primary_name': ingredient_name,
                                    'category_id': category_id,
                                    'nutrition_id': nutrition_id,
                                    'language': lang,
                                    'form': 'singular',
                                    'name': singular_name,
                                    'synonyms': names_doc['names'][lang]['singular']['synonyms'],
                                    'created_at': datetime.utcnow(),
                                    'last_updated': datetime.utcnow()
                                }
                                ingredient_names_collection.update_one(
                                    {
                                        'primary_name': ingredient_name,
                                        'language': lang,
                                        'form': 'singular'
                                    },
                                    {'$set': singular_doc},
                                    upsert=True
                                )

                            # Handle plural form
                            plural_name = names_doc['names'][lang]['plural']['name']
                            if plural_name:  # Only create record if plural name exists
                                plural_doc = {
                                    'primary_name': ingredient_name,
                                    'category_id': category_id,
                                    'nutrition_id': nutrition_id,
                                    'language': lang,
                                    'form': 'plural',
                                    'name': plural_name,
                                    'synonyms': names_doc['names'][lang]['plural']['synonyms'],
                                    'created_at': datetime.utcnow(),
                                    'last_updated': datetime.utcnow()
                                }
                                ingredient_names_collection.update_one(
                                    {
                                        'primary_name': ingredient_name,
                                        'language': lang,
                                        'form': 'plural'
                                    },
                                    {'$set': plural_doc},
                                    upsert=True
                                )
                    except Exception as e:
                        print(f"Error processing names for ingredient {ingredient_name}: {str(e)}")
                        continue
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
                        IMPORTANT: Your response must be valid JSON - do not include any explanatory text before or after the JSON
                        IMPORTANT: take calroy data from https://www.fatsecret.com/calories-nutrition/usda or https://fdc.nal.usda.gov/ other but write me the source

                        {{
                            "name": "New recipe name",
                            "ingredients": ["List of ingredients"],
                            "base_ingredient_name": ["List of all base ingredients without any modifications / counts, singular and plural for this ingredientwrite in english "],                            
                            "instructions": ["Step by step instructions"],
                            "prep_time": "Preparation time in minutes",
                            "cook_time": "Cooking time in minutes",
                            "difficulty": "One of [Easy, Medium, Hard]",
                            "servings": "Number of servings",
                            "cusine": "ex: Amirican / Asian / French",
                            "course": "One of [Breakfast, Lunch, Dinner, Snack, Any]",
                            "macronutrients": {{     
                                "data_source": "site name",                           
                                "weight: "gr/ml",                              
                                "proteins": "protein content in grams (e.g., '15.2g')",
                                "carbohydrates": "carbohydrate content in grams (e.g., '45.2g')",
                                "fats": "fat content in grams (e.g., '12.2g')",
                                "calories": "calorie content (e.g., '350.2kcal')"
                            }},
                            "macronutrients_by_ingredient": {{
                                "base_ingredient_name": {{
                                    "category": "one of the list [Fruits,Other,Eggs,Grains,Legumes,Dairy,Vegetables/Fruits,Fish,Fat And Oils,Vegetables,Meat,Herb,Leafy Green,Fruit Juice,Nut,Mushroom,Soy,Alcoholic,Fortified Wine,Nut Recipes,Seed,Dried Fruit,Spice,Citrus,Dairy Alternatives,Sweeteners,Condiment,Root Vegetable,Shellfish,Seafood,Liqueur,Alcohol,Poultry,Olive,Nuts and Seeds,Herbs and Spices,Berry,Tree Nut,Fruit And Oils,Sauces,Liquor,Beverages]",                             
                                    "possible_measurement": ["e.g., g, ml, tbsp, tsp, cup, etc."],
                                    "base_ingredient_name": ["List of base ingredients without any modifications / counts, singular and plural for this ingredientwrite in english "],
                                    "names": {{
                                        "english": {{
                                            "name": {{
                                                "singular": "english name",
                                                "plural": "english names"
                                            }},
                                            "synonyms": ["english synonym 1", "english synonym 2"]
                                        }},
                                        "russian": {{
                                            "name": {{
                                                "singular": "russian name",
                                                "plural": "russian names"
                                            }},
                                            "synonyms": ["russian synonym 1", "russian synonym 2"]
                                        }},
                                        "spanish": {{
                                            "name": {{
                                                "singular": "spanish name",
                                                "plural": "spanish names"
                                            }},
                                            "synonyms": ["spanish synonym 1", "spanish synonym 2"]
                                        }},
                                        "hebrew": {{
                                            "name": {{
                                                "singular": "hebrew name",
                                                "plural": "hebrew names"
                                            }},
                                            "synonyms": ["hebrew synonym 1", "hebrew synonym 2"]
                                        }}
                                    }},
                                    "data_source": "site name",
                                    "weight": "Actual weight in grams or milliliters (e.g., '100.2g' or '250ml')",
                                    "proteins": "Calculate actual protein content in grams (e.g., '5.3g')",
                                    "carbohydrates": "Calculate actual carbohydrate content in grams (e.g., '20.2g')",
                                    "fats": "Calculate actual fat content in grams (e.g., '3.2g')",
                                    "calories": "Calculate actual calorie content (e.g., '120.2kcal')",
                                    "average_weight": "Standard serving size in grams or milliliters",
                                    "proteins_per_100g": "Calculate protein content per 100g (e.g., '5.3g') - must be a float number and must filled",
                                    "carbohydrates_per_100g": "Calculate carbohydrate content per 100g (e.g., '20.1g') - must be a float number and must filled",
                                    "fats_per_100g": "Calculate fat content per 100g (e.g., '3.1g') - must be a float number and must filled",
                                    "calories_per_100g": "Calculate calories per 100g (e.g., '120.2kcal') - must be a float number and must filled"
                                }}
                            }},
                            "macronutrients_per_for_this_meal_100g": {{                                
                                "proteins": "Calculate total protein content per 100g of the final dish - must be a float number and must filled",
                                "carbohydrates": "Calculate total carbohydrate content per 100g of the final dish - must be a float number and must filled",
                                "fats": "Calculate total fat content per 100g of the final dish - must be a float number and must filled",
                                "calories": "Calculate total calories per 100g of the final dish - must be a float number and must filled"
                            }},
                            "kosher": {{
                                "is_kosher": "Yes/No",
                                "why": "description-exp milk and meat, prey meat -Meat is not kosher"
                            }},
                            "halal": {{
                                "is_halal": "Yes/No",
                                "why": "description-exp"
                            }},
                            "gluten_free": {{
                                "is_gluten_free": "Yes/No",
                                "why": "description-exp"
                            }},
                            "dairy_free": {{
                                "is_dairy_free": "Yes/No",
                                "why": "description-exp"
                            }},
                            "low_carb": {{
                                "is_low_carb": "Yes/No",
                                "why": "description-exp"
                            }},
                            "diabetic_friendly": {{
                                "is_diabetic_friendly": "Yes/No",
                                "why": "description-exp"
                            }},
                            "heart_healthy": {{
                                "is_heart_healthy": "Yes/No",
                                "why": "description-exp"
                            }},
                            "health_rank": "number between 1-100",
                            "tasty_rank": "number between 1-100",
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
            recipe_id = save_recipe_to_mongodb(new_recipe,recipe_info)
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

async def check_recipes_exist(titles: List[str]) -> Dict[str, bool]:
    """
    Check if multiple recipes exist in the database at once.
    
    Args:
        titles (List[str]): List of recipe titles to check
        
    Returns:
        Dict[str, bool]: Dictionary mapping recipe titles to their existence status
    """
    try:
        # Create a query to find all recipes with the given titles
        query = {'name': {'$in': titles}}
        existing_recipes = gpt_recipes_collection.find(query, {'name': 1})
        
        # Create a set of existing recipe names for O(1) lookup
        existing_names = {recipe['name'] for recipe in existing_recipes}
        
        # Create a dictionary mapping each title to its existence status
        return {title: title in existing_names for title in titles}
    except Exception as e:
        print(f"Error checking recipe existence: {str(e)}")
        return {title: False for title in titles}

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

def get_random_recipe_sample(sample_size: int = 1000) -> List[Dict]:
    """
    Get a random sample of recipes from the database.
    
    Args:
        sample_size (int): Number of recipes to sample (default: 1000)
        
    Returns:
        List[Dict]: List of randomly sampled recipes
    """
    try:
        # Use MongoDB's $sample aggregation to get random documents
        pipeline = [
            {"$sample": {"size": sample_size}}
        ]
        
        # Execute the aggregation
        sampled_recipes = list(recipes_collection.aggregate(pipeline))
        
        print(f"Successfully sampled {len(sampled_recipes)} recipes")
        return sampled_recipes
        
    except Exception as e:
        print(f"Error sampling recipes: {str(e)}")
        return []


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

            # Get all recipe titles in the batch
            recipe_titles = [recipe.get('title', '') for recipe in recipes]
            
            # Check which recipes already exist
            existing_status = await check_recipes_exist(recipe_titles)
            
            # Filter out existing recipes
            new_recipes = [recipe for recipe in recipes if not existing_status.get(recipe.get('title', ''), False)]
            
            if not new_recipes:
                print("All recipes in this batch already exist")
                processed += len(recipes)
                skipped += len(recipes)
                batch_number += 1
                continue

            # Process the batch
            batch_processed, batch_successful = await process_recipe_batch(new_recipes, model)
            
            # Update statistics
            processed += len(recipes)
            successful += batch_successful
            skipped += len(recipes) - len(new_recipes)

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


def save_validation_error(ingredient_name: str, error_message: str, nutrition_data: Dict, category: str = None):
    """
    Save validation error to a collection for manual review.
    
    Args:
        ingredient_name (str): Name of the ingredient
        error_message (str): Validation error message
        nutrition_data (Dict): The nutrition data that failed validation
        category (str): Category of the ingredient
    """
    try:
        error_doc = {
            'ingredient_name': ingredient_name,
            'error_message': error_message,
            'nutrition_data': nutrition_data,
            'category': category,
            'should_check': True,
            'created_at': datetime.utcnow(),
            'status': 'pending'  # pending, reviewed, fixed, ignored
        }
        
        # Create or get the validation_errors collection
        validation_errors_collection = recipes_collection.database['validation_errors']
        
        # Insert the error document
        validation_errors_collection.insert_one(error_doc)
        
    except Exception as e:
        print(f"Error saving validation error: {str(e)}")

def validate_nutritional_values(nutrition_data: Dict, category: str = None) -> Tuple[bool, str]:
    """
    Validate nutritional values for an ingredient.
    
    Args:
        nutrition_data (Dict): Dictionary containing nutritional values
        category (str): Category of the ingredient (e.g., 'Alcoholic', 'Beverages')
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Extract values and convert to float
        def extract_float(value: str) -> float:
            if isinstance(value, (int, float)):
                return float(value)
            # Remove units and convert to float
            return float(str(value).replace('g', '').replace('kcal', '').strip())

        # Get values
        proteins = extract_float(nutrition_data.get('proteins_per_100g', '0'))
        carbs = extract_float(nutrition_data.get('carbohydrates_per_100g', '0'))
        fats = extract_float(nutrition_data.get('fats_per_100g', '0'))
        calories = extract_float(nutrition_data.get('calories_per_100g', '0'))

        # Check if this is an alcoholic beverage
        is_alcoholic = category in ['Alcoholic', 'Alcohol', 'Liquor', 'Fortified Wine', 'Liqueur'] or \
                      any(alcohol_term in str(category).lower() for alcohol_term in ['wine', 'beer', 'spirit', 'liquor'])

        if is_alcoholic:
            # Special validation for alcoholic beverages
            if not (0 <= proteins <= 5):
                error_msg = f"Invalid protein value for alcoholic beverage: {proteins}g (should be between 0-5g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= carbs <= 30):
                error_msg = f"Invalid carbohydrate value for alcoholic beverage: {carbs}g (should be between 0-30g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= fats <= 5):
                error_msg = f"Invalid fat value for alcoholic beverage: {fats}g (should be between 0-5g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= calories <= 350):
                error_msg = f"Invalid calorie value for alcoholic beverage: {calories}kcal (should be between 0-350kcal)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg

        else:
            # Regular food validation
            if not (0 <= proteins <= 100):
                error_msg = f"Invalid protein value: {proteins}g (should be between 0-100g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= carbs <= 100):
                error_msg = f"Invalid carbohydrate value: {carbs}g (should be between 0-100g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= fats <= 100):
                error_msg = f"Invalid fat value: {fats}g (should be between 0-100g)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg
            if not (0 <= calories <= 900):
                error_msg = f"Invalid calorie value: {calories}kcal (should be between 0-900kcal)"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg

            # Validate total macronutrients don't exceed 100g
            total_macros = proteins + carbs + fats
            if total_macros > 100:
                error_msg = f"Total macronutrients ({total_macros}g) exceed 100g"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg

            # Validate calories match macronutrients (roughly)
            calculated_calories = (proteins * 4) + (carbs * 4) + (fats * 9)
            if abs(calculated_calories - calories) > 50:
                error_msg = f"Calorie calculation mismatch: calculated {calculated_calories}kcal vs provided {calories}kcal"
                save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
                return False, error_msg

        return True, "Valid nutritional values"

    except (ValueError, TypeError) as e:
        error_msg = f"Error converting values: {str(e)}"
        save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
        return False, error_msg
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        save_validation_error(nutrition_data.get('ingredient_name', 'Unknown'), error_msg, nutrition_data, category)
        return False, error_msg

#
# if __name__ == "__main__":
#     # Get a random sample of 1000 recipes
#     print("Starting to sample 1000 random recipes...")
#     sample_recipes = get_random_recipe_sample(1000)
#
#     if sample_recipes:
#         print(f"Successfully sampled {len(sample_recipes)} recipes")
#         print("Starting recipe variation generation...")
#         # Process the sample with parallel processing
#         asyncio.run(generate_recipe_variations(
#             recipes=sample_recipes,
#             batch_size=10,
#             model="google/gemini-2.5-flash-preview",
#             max_concurrent=10
#         ))
#     else:
#         print("Failed to get recipe sample. Exiting...")
