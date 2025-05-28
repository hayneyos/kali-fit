import os
import json
from typing import List, Dict, Set
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime

# Load environment variables
load_dotenv()
from mongo_handler import *

def create_text_index():
    """
    Create text index for recipe search with default language.
    """
    try:
        # Drop existing text index if it exists
        recipes_collection.drop_index("name_text_ingredients_text_instructions_text")
    except Exception:
        pass  # Index might not exist
        
    # Create new text index with default language
    recipes_collection.create_index([
        ("name", "text"),
        ("ingredients", "text"),
        ("instructions", "text")
    ], default_language="none")  # Use 'none' to disable language-specific features
    
    print("Created text index for recipe search")


def store_recipe_in_mongodb(recipe_data: Dict) -> bool:
    """
    Store a recipe in MongoDB if it doesn't exist.

    Args:
        recipe_data (Dict): Recipe data to store

    Returns:
        bool: True if recipe was stored or already exists, False if there was an error
    """
    try:
        # Use recipe_id as the unique identifier
        recipe_id = recipe_data['_metadata']['recipe_id']

        # Check if recipe already exists
        existing_recipe = recipes_collection.find_one({'recipe_id': recipe_id})
        if existing_recipe:
            print(f"Recipe {recipe_id} already exists in database")
            return True

        # Add timestamp for when the recipe was added
        recipe_data['_metadata']['added_at'] = datetime.utcnow()

        # Remove any language specification from text fields
        if 'language' in recipe_data:
            del recipe_data['language']

        # Clean text fields to remove language specifications
        for field in ['name', 'description', 'instructions']:
            if field in recipe_data and isinstance(recipe_data[field], str):
                recipe_data[field] = recipe_data[field].replace('en-US', '').strip()
            elif field in recipe_data and isinstance(recipe_data[field], list):
                recipe_data[field] = [item.replace('en-US', '').strip() if isinstance(item, str) else item
                                      for item in recipe_data[field]]

        # Insert the recipe
        result = recipes_collection.insert_one(recipe_data)
        print(f"Stored recipe {recipe_id} with MongoDB ID: {result.inserted_id}")
        return True

    except Exception as e:
        print(f"Error storing recipe {recipe_data.get('_metadata', {}).get('recipe_id', 'unknown')}: {str(e)}")
        return False


def get_recipe_files(base_path: str = "/home/github/recipes") -> List[Dict]:
    """
    Get all recipe files from the specified folder structure and store them in MongoDB.
    
    Args:
        base_path (str): Base path to the recipes directory
        
    Returns:
        List[Dict]: List of dictionaries containing recipe data and metadata
    """
    recipes = []
    base_path = Path(base_path)
    
    # Check if base path exists
    if not base_path.exists():
        raise FileNotFoundError(f"Base path {base_path} does not exist")
    
    # Get all index subdirectories (letters and digits)
    index_path = base_path / "index"
    if not index_path.exists():
        raise FileNotFoundError(f"Index directory {index_path} does not exist")
    
    # Iterate through all subdirectories in index (letters and numbers)
    for category_dir in index_path.iterdir():
        if not category_dir.is_dir():
            continue
            
        # Look for JSON files directly in the category directory
        for json_file in category_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    recipe_data = json.load(f)
                    
                # Add metadata about the file location
                recipe_data['_metadata'] = {
                    'file_path': str(json_file),
                    'category': category_dir.name,
                    'recipe_id': json_file.stem,  # Use filename without extension as recipe_id
                    'source': 'json_file'
                }
                
                # Store recipe in MongoDB
                if store_recipe_in_mongodb(recipe_data):
                    recipes.append(recipe_data)
                    
            except json.JSONDecodeError as e:
                print(f"Error reading {json_file}: {str(e)}")
            except Exception as e:
                print(f"Unexpected error processing {json_file}: {str(e)}")
    
    return recipes

def get_recipe_files_by_category(category: str, base_path: str = "/home/github/recipes") -> List[Dict]:
    """
    Get recipes for a specific category from MongoDB.
    
    Args:
        category (str): Category to filter by (e.g., 'a', '1')
        base_path (str): Not used, kept for backward compatibility
        
    Returns:
        List[Dict]: List of dictionaries containing recipe data and metadata
    """
    try:
        # Query MongoDB for recipes in the specified category
        cursor = recipes_collection.find(
            {"_metadata.category": category},
            {"_id": 0}  # Exclude MongoDB _id from results
        )
        
        # Convert cursor to list
        recipes = list(cursor)
        
        print(f"Found {len(recipes)} recipes in category '{category}' from database")
        return recipes
        
    except Exception as e:
        print(f"Error querying recipes for category '{category}': {str(e)}")
        return []

def get_recipe_by_id(recipe_id: str) -> Dict:
    """
    Get a specific recipe by its ID from MongoDB.
    
    Args:
        recipe_id (str): The recipe ID to search for
        
    Returns:
        Dict: Recipe data if found, None otherwise
    """
    try:
        recipe = recipes_collection.find_one(
            {"_metadata.recipe_id": recipe_id},
            {"_id": 0}  # Exclude MongoDB _id from results
        )
        
        if recipe:
            print(f"Found recipe with ID: {recipe_id}")
        else:
            print(f"No recipe found with ID: {recipe_id}")
            
        return recipe
        
    except Exception as e:
        print(f"Error querying recipe with ID '{recipe_id}': {str(e)}")
        return None

def search_recipes(query: str, limit: int = 10) -> List[Dict]:
    """
    Search recipes by name or ingredients using MongoDB text search.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results to return
        
    Returns:
        List[Dict]: List of matching recipes
    """
    try:
        # Create text index if it doesn't exist
        recipes_collection.create_index([
            ("name", "text"),
            ("ingredients", "text"),
            ("instructions", "text")
        ])
        
        # Search using MongoDB text search
        cursor = recipes_collection.find(
            {"$text": {"$search": query}},
            {
                "_id": 0,
                "score": {"$meta": "textScore"}
            }
        ).sort([
            ("score", {"$meta": "textScore"})
        ]).limit(limit)
        
        recipes = list(cursor)
        print(f"Found {len(recipes)} recipes matching query: {query}")
        return recipes
        
    except Exception as e:
        print(f"Error searching recipes: {str(e)}")
        return []

def get_all_recipe_files(base_path: str = "/home/github/recipes") -> Dict[str, List[Path]]:
    """
    Build a list of all recipe files organized by category.
    Files are sorted by name within each category.
    
    Args:
        base_path (str): Base path to the recipes directory
        
    Returns:
        Dict[str, List[Path]]: Dictionary mapping categories to sorted lists of recipe file paths
    """
    recipe_files = {}
    base_path = Path(base_path)
    
    # Check if base path exists
    if not base_path.exists():
        raise FileNotFoundError(f"Base path {base_path} does not exist")
    
    # Get all index subdirectories (letters and digits)
    index_path = base_path / "index"
    if not index_path.exists():
        raise FileNotFoundError(f"Index directory {index_path} does not exist")
    
    # Iterate through all subdirectories in index (letters and numbers)
    for category_dir in sorted(index_path.iterdir()):  # Sort categories
        if not category_dir.is_dir():
            continue
            
        category = category_dir.name
        recipe_files[category] = []
        
        # Look for JSON files directly in the category directory
        for json_file in category_dir.glob("*.json"):
            recipe_files[category].append(json_file)
            
        # Sort files by name within each category
        recipe_files[category].sort(key=lambda x: x.name.lower())  # Case-insensitive sort
    
    return recipe_files

def get_existing_recipe_ids() -> Set[str]:
    """
    Get a set of all recipe IDs that already exist in the database.
    
    Returns:
        Set[str]: Set of existing recipe IDs
    """
    try:
        # Get all recipe IDs from the database
        cursor = recipes_collection.find({}, {"_metadata.recipe_id": 1})
        existing_ids = {doc["_metadata"]["recipe_id"] for doc in cursor if "_metadata" in doc and "recipe_id" in doc["_metadata"]}
        print(f"Found {len(existing_ids)} existing recipes in database")
        return existing_ids
    except Exception as e:
        print(f"Error getting existing recipe IDs: {str(e)}")
        return set()


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
            'prep_time': recipe.get('prep_time'),
            'cook_time': recipe.get('cook_time'),
            'difficulty': recipe.get('difficulty'),
            'servings': recipe.get('servings'),
            'created_at': datetime.datetime.utcnow(),
            'source_model': recipe.get('source_model'),
            'input_ingredients': recipe.get('input_ingredients', [])
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
                        'created_at': datetime.datetime.utcnow()
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
                        'created_at': datetime.datetime.utcnow(),
                        'last_updated': datetime.datetime.utcnow()
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
                        'last_updated': datetime.datetime.utcnow()
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

def build_and_store_recipes(base_path: str = "/home/github/recipes") -> Dict:
    """
    Read all recipes from the file system and store them in MongoDB.
    This function will process all JSON files in the recipes directory structure.
    
    Args:
        base_path (str): Base path to the recipes directory
        
    Returns:
        Dict: Statistics about the operation
    """
    # Create text index before starting
    create_text_index()
    
    # Get all recipe files and existing recipe IDs
    print("Building list of recipe files...")
    recipe_files = get_all_recipe_files(base_path)
    existing_ids = get_existing_recipe_ids()
    
    stats = {
        'total_files': 0,
        'successfully_stored': 0,
        'already_exist': 0,
        'errors': 0,
        'categories_processed': 0,
        'skipped_files': 0
    }
    
    print(f"\nStarting to process recipes from {base_path}")
    print(f"Found {sum(len(files) for files in recipe_files.values())} total recipe files")
    print(f"Found {len(existing_ids)} existing recipes in database")
    
    # Iterate through all categories in sorted order
    for category in sorted(recipe_files.keys()):
        files = recipe_files[category]
        print(f"\nProcessing category: {category}")
        category_stats = {
            'files': len(files),
            'stored': 0,
            'existing': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # Process each file in the category
        for json_file in files:  # Files are already sorted
            recipe_id = json_file.stem
            stats['total_files'] += 1
            
            # Skip if recipe already exists
            if recipe_id in existing_ids:
                stats['already_exist'] += 1
                category_stats['existing'] += 1
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    recipe_data = json.load(f)
                    
                # Add metadata about the file location
                recipe_data['_metadata'] = {
                    'file_path': str(json_file),
                    'category': category,
                    'recipe_id': recipe_id,
                    'source': 'json_file',
                    'processed_at': datetime.utcnow()
                }
                
                # Store recipe in MongoDB
                if store_recipe_in_mongodb(recipe_data):
                    stats['successfully_stored'] += 1
                    category_stats['stored'] += 1
                else:
                    stats['errors'] += 1
                    category_stats['errors'] += 1
                    
            except json.JSONDecodeError as e:
                print(f"Error reading {json_file}: {str(e)}")
                stats['errors'] += 1
                category_stats['errors'] += 1
            except Exception as e:
                print(f"Unexpected error processing {json_file}: {str(e)}")
                stats['errors'] += 1
                category_stats['errors'] += 1
        
        # Print category statistics
        print(f"Category {category} statistics:")
        print(f"  Files found: {category_stats['files']}")
        print(f"  Successfully stored: {category_stats['stored']}")
        print(f"  Already exist: {category_stats['existing']}")
        print(f"  Errors: {category_stats['errors']}")
        
        stats['categories_processed'] += 1
    
    # Print final statistics
    print("\nFinal Statistics:")
    print(f"Total categories processed: {stats['categories_processed']}")
    print(f"Total files found: {stats['total_files']}")
    print(f"Successfully stored: {stats['successfully_stored']}")
    print(f"Already exist in database: {stats['already_exist']}")
    print(f"Errors encountered: {stats['errors']}")
    
    return stats

if __name__ == "__main__":
    # Example usage
    try:
        # Build and store all recipes
        stats = build_and_store_recipes()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Close MongoDB connection
        client.close()
        print("MongoDB connection closed")
