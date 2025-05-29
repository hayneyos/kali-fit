import os
from urllib.parse import quote_plus
from pymongo import MongoClient
from typing import List, Dict, Optional
from datetime import datetime

from backend.app_recipe.utils.base.mongo_client import get_mongo_client, db


def search_recipes(
        query: Optional[Dict] = None,
        limit: int = 10,
        skip: int = 0,
        sort_by: str = "name",
        sort_order: int = 1
) -> List[Dict]:
    """
    Search for recipes in the database with various filters.
    
    Args:
        query (Dict, optional): MongoDB query dictionary
        limit (int): Maximum number of recipes to return
        skip (int): Number of recipes to skip
        sort_by (str): Field to sort by
        sort_order (int): Sort order (1 for ascending, -1 for descending)
        
    Returns:
        List[Dict]: List of matching recipes
    """
    try:
        client = get_mongo_client()
        db = client['recipe_db_v3']
        recipes_collection = db['gpt_recipes']

        # Build the query
        search_query = query or {}

        # Execute the search
        cursor = recipes_collection.find(
            search_query,
            {
                '_id': 1,
                'name': 1,
                'ingredients': 1,
                'instructions': 1,
                'prep_time': 1,
                'cook_time': 1,
                'difficulty': 1,
                'servings': 1,
                'total_proteins': 1,
                'total_carbohydrates': 1,
                'total_fats': 1,
                'total_calories': 1,
                'health_benefits': 1,
                'suitable_diets': 1,
                'unsuitable_diets': 1,
                'created_at': 1
            }
        ).sort(sort_by, sort_order).skip(skip).limit(limit)

        # Convert cursor to list
        recipes = list(cursor)

        # Convert ObjectId to string for JSON serialization
        for recipe in recipes:
            recipe['_id'] = str(recipe['_id'])
            if 'created_at' in recipe:
                recipe['created_at'] = recipe['created_at'].isoformat()

        return recipes

    except Exception as e:
        print(f"Error searching recipes: {str(e)}")
        raise
    finally:
        if 'client' in locals():
            client.close()


def search_recipes_by_ingredients(
        ingredients: List[str],
        limit: int = 10,
        skip: int = 0
) -> List[Dict]:
    """
    Search for recipes that contain specific ingredients.
    
    Args:
        ingredients (List[str]): List of ingredients to search for
        limit (int): Maximum number of recipes to return
        skip (int): Number of recipes to skip
        
    Returns:
        List[Dict]: List of matching recipes
    """
    try:
        # Create a case-insensitive regex pattern for each ingredient
        ingredient_patterns = [{'ingredients': {'$regex': ingredient, '$options': 'i'}}
                               for ingredient in ingredients]

        # Combine patterns with OR operator
        query = {'$or': ingredient_patterns}

        return search_recipes(query=query, limit=limit, skip=skip)

    except Exception as e:
        print(f"Error searching recipes by ingredients: {str(e)}")
        raise


def search_recipes_by_diet(
        diet_type: str,
        limit: int = 10,
        skip: int = 0
) -> List[Dict]:
    """
    Search for recipes suitable for a specific diet type.
    
    Args:
        diet_type (str): Diet type to search for (e.g., 'Vegan', 'Gluten-free')
        limit (int): Maximum number of recipes to return
        skip (int): Number of recipes to skip
        
    Returns:
        List[Dict]: List of matching recipes
    """
    try:
        # Create case-insensitive regex pattern for diet type
        query = {
            'suitable_diets': {'$regex': diet_type, '$options': 'i'}
        }

        return search_recipes(query=query, limit=limit, skip=skip)

    except Exception as e:
        print(f"Error searching recipes by diet: {str(e)}")
        raise


def search_recipes_advanced(
        ingredients=None,
        diet_type=None,
        min_proteins=None,
        max_proteins=None,
        min_carbs=None,
        max_carbs=None,
        min_fats=None,
        max_fats=None,
        min_calories=None,
        max_calories=None,
        limit=10,
        skip=0
):
    query = {}

    # מרכיבים
    if ingredients:
        query["ingredients"] = {"$all": ingredients}

    # סוג תזונה
    if diet_type:
        query["suitable_diets"] = diet_type

    # ערכים תזונתיים – המרה ממחרוזות
    def build_range_query(field_name, min_val, max_val, unit):
        expr = {}
        if min_val is not None:
            expr["$gte"] = f"{min_val}{unit}"
        if max_val is not None:
            expr["$lte"] = f"{max_val}{unit}"
        if expr:
            query[field_name] = expr

    build_range_query("total_proteins", min_proteins, max_proteins, "g")
    build_range_query("total_carbohydrates", min_carbs, max_carbs, "g")
    build_range_query("total_fats", min_fats, max_fats, "g")
    build_range_query("total_calories", min_calories, max_calories, "kcal")

    return list(db.gpt_recipes.find(query).skip(skip).limit(limit))


def search_recipes_by_nutrition(
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
) -> List[Dict]:
    """
    Search for recipes based on nutritional requirements.
    
    Args:
        min_proteins (float, optional): Minimum protein content
        max_proteins (float, optional): Maximum protein content
        min_carbs (float, optional): Minimum carbohydrate content
        max_carbs (float, optional): Maximum carbohydrate content
        min_fats (float, optional): Minimum fat content
        max_fats (float, optional): Maximum fat content
        min_calories (float, optional): Minimum calorie content
        max_calories (float, optional): Maximum calorie content
        limit (int): Maximum number of recipes to return
        skip (int): Number of recipes to skip
        
    Returns:
        List[Dict]: List of matching recipes
    """
    try:
        query = {}

        # Add nutrition filters if provided
        if min_proteins is not None:
            query['total_proteins'] = {'$gte': f"{min_proteins}g"}
        if max_proteins is not None:
            query['total_proteins'] = {'$lte': f"{max_proteins}g"}
        if min_carbs is not None:
            query['total_carbohydrates'] = {'$gte': f"{min_carbs}g"}
        if max_carbs is not None:
            query['total_carbohydrates'] = {'$lte': f"{max_carbs}g"}
        if min_fats is not None:
            query['total_fats'] = {'$gte': f"{min_fats}g"}
        if max_fats is not None:
            query['total_fats'] = {'$lte': f"{max_fats}g"}
        if min_calories is not None:
            query['total_calories'] = {'$gte': f"{min_calories}kcal"}
        if max_calories is not None:
            query['total_calories'] = {'$lte': f"{max_calories}kcal"}

        return search_recipes(query=query, limit=limit, skip=skip)

    except Exception as e:
        print(f"Error searching recipes by nutrition: {str(e)}")
        raise
