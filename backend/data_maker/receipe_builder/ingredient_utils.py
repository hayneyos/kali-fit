import pandas as pd
from typing import Dict, List, Optional
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

from backend.data_maker.receipe_builder.ingredient_normalizer import normalized_ingredients_collection
from mongo_handler import  *
# Load environment variables
load_dotenv()


def flatten_names_data(names_data: List[Dict]) -> List[Dict]:
    """
    Flatten the nested names dictionary in the normalized ingredients data.
    
    Args:
        names_data (List[Dict]): List of normalized ingredient documents from MongoDB
        
    Returns:
        List[Dict]: List of documents with flattened name fields
    """
    flattened_data = []
    for doc in names_data:
        # Get the primary name and its variations
        primary_name = doc.get('primary_name', '')
        variations = doc.get('variations', [])
        
        # Create a document for the primary name
        primary_doc = {
            '_id': doc.get('_id'),
            'primary_name': primary_name,
            'created_at': doc.get('created_at'),
            'last_updated': doc.get('last_updated')
        }
        
        # Add all language names from the first variation (they should be the same for all variations)
        if variations:
            first_variation = variations[0]
            names = first_variation.get('names', {})
            for lang in ['english', 'russian', 'spanish', 'hebrew']:
                lang_data = names.get(lang, {})
                primary_doc.update({
                    f'{lang}_name': lang_data.get('name', ''),
                    f'{lang}_synonyms': lang_data.get('synonyms', [])
                })
            
            # Add nutrition data from first variation
            nutrition = first_variation.get('nutrition', {})
            primary_doc.update({
                'nutrition_id': nutrition.get('nutrition_id'),
                'weight': nutrition.get('weight'),
                'proteins': nutrition.get('proteins'),
                'carbohydrates': nutrition.get('carbohydrates'),
                'fats': nutrition.get('fats'),
                'calories': nutrition.get('calories'),
                'proteins_per_100g': nutrition.get('proteins_per_100g'),
                'carbohydrates_per_100g': nutrition.get('carbohydrates_per_100g'),
                'fats_per_100g': nutrition.get('fats_per_100g'),
                'calories_per_100g': nutrition.get('calories_per_100g')
            })
        
        flattened_data.append(primary_doc)
        
        # Add all variations as separate documents
        for variation in variations:
            var_doc = {
                '_id': variation.get('original_id'),
                'primary_name': variation.get('original_name', ''),
                'created_at': doc.get('created_at'),
                'last_updated': doc.get('last_updated')
            }
            
            # Add language names
            names = variation.get('names', {})
            for lang in ['english', 'russian', 'spanish', 'hebrew']:
                lang_data = names.get(lang, {})
                var_doc.update({
                    f'{lang}_name': lang_data.get('name', ''),
                    f'{lang}_synonyms': lang_data.get('synonyms', [])
                })
            
            # Add nutrition data
            nutrition = variation.get('nutrition', {})
            var_doc.update({
                'nutrition_id': nutrition.get('nutrition_id'),
                'weight': nutrition.get('weight'),
                'proteins': nutrition.get('proteins'),
                'carbohydrates': nutrition.get('carbohydrates'),
                'fats': nutrition.get('fats'),
                'calories': nutrition.get('calories'),
                'proteins_per_100g': nutrition.get('proteins_per_100g'),
                'carbohydrates_per_100g': nutrition.get('carbohydrates_per_100g'),
                'fats_per_100g': nutrition.get('fats_per_100g'),
                'calories_per_100g': nutrition.get('calories_per_100g')
            })
            
            flattened_data.append(var_doc)
    
    return flattened_data

def get_ingredients_dataframe() -> pd.DataFrame:
    """
    Combine data from MongoDB collections into a single DataFrame:
    - normalized_ingredients_v1
    - ingredient_categories_v3
    
    Returns:
        pd.DataFrame: Combined ingredient data with nutrition information
    """
    try:
        # Get all documents from each collection
        categories_data = list(ingredient_categories_collection.find({}))
        names_data = list(normalized_ingredients_collection.find({}))

        # Flatten the names data before creating DataFrame
        flattened_names_data = flatten_names_data(names_data)
        
        # Create DataFrames
        categories_df = pd.DataFrame(categories_data)
        names_df = pd.DataFrame(flattened_names_data)
        
        # Print column names for debugging
        print("\nCategories DataFrame columns:", categories_df.columns.tolist())
        print("Names DataFrame columns:", names_df.columns.tolist())
        
        # Merge DataFrames
        merged_df = pd.merge(
            names_df,
            categories_df,
            left_on='category_id',
            right_on='_id',
            how='left',
            suffixes=('', '_category')
        )
        
        # Clean up the DataFrame
        # Drop duplicate columns
        merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]
        
        # Print merged columns for debugging
        print("\nMerged DataFrame columns:", merged_df.columns.tolist())
        
        # Select and rename columns
        columns_to_keep = {
            '_id': 'names_id',
            '_id_category': 'category_id',
            'nutrition_id': 'nutrition_id',
            'primary_name': 'ingredient_name',
            'name': 'category_name',
            'weight': 'weight',
            'proteins': 'proteins',
            'carbohydrates': 'carbohydrates',
            'fats': 'fats',
            'calories': 'calories',
            'proteins_per_100g': 'proteins_per_100g',
            'carbohydrates_per_100g': 'carbohydrates_per_100g',
            'fats_per_100g': 'fats_per_100g',
            'calories_per_100g': 'calories_per_100g',
            'english_name': 'english_name',
            'english_synonyms': 'english_synonyms',
            'russian_name': 'russian_name',
            'russian_synonyms': 'russian_synonyms',
            'spanish_name': 'spanish_name',
            'spanish_synonyms': 'spanish_synonyms',
            'hebrew_name': 'hebrew_name',
            'hebrew_synonyms': 'hebrew_synonyms',
            'last_updated': 'last_updated'
        }
        
        # Check which columns exist in the merged DataFrame
        existing_columns = [col for col in columns_to_keep.keys() if col in merged_df.columns]
        if not existing_columns:
            raise ValueError("No matching columns found in merged DataFrame")
            
        # Create final DataFrame with only existing columns
        final_df = merged_df[existing_columns].rename(columns=columns_to_keep)
        
        # Convert numeric columns
        numeric_columns = [
            'proteins', 'carbohydrates', 'fats', 'calories',
            'proteins_per_100g', 'carbohydrates_per_100g', 'fats_per_100g', 'calories_per_100g'
        ]
        
        for col in numeric_columns:
            if col in final_df.columns:
                final_df[col] = pd.to_numeric(
                    final_df[col].astype(str).str.replace('g', '').str.replace('kcal', ''),
                    errors='coerce'
                )
        
        # Sort by ingredient name
        final_df = final_df.sort_values('ingredient_name')
        
        print(f"\nCreated DataFrame with {len(final_df)} ingredients")
        print("\nColumns in the final DataFrame:")
        print(final_df.columns.tolist())
        print("\nSample of the data:")
        print(final_df.head())
        
        return final_df
        
    except Exception as e:
        print(f"Error creating ingredients DataFrame: {str(e)}")
        print("\nDebug information:")
        print(f"Number of category records: {len(categories_data)}")
        print(f"Number of name records: {len(names_data)}")
        raise
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed")


def save_ingredients_to_csv(df: pd.DataFrame, filename: str = "ingredients_data.csv"):
    """
    Save the ingredients DataFrame to a CSV file.

    Args:
        df (pd.DataFrame): The DataFrame to save
        filename (str): Name of the CSV file
    """
    try:
        df.to_csv(filename, index=False)
        print(f"Saved ingredients data to {filename}")
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")


def get_ingredient_stats(df: pd.DataFrame) -> Dict:
    """
    Get statistics about the ingredients data.

    Args:
        df (pd.DataFrame): The ingredients DataFrame

    Returns:
        Dict: Statistics about the data
    """
    stats = {
        'total_ingredients': len(df),
        'categories': df['category_name'].nunique(),
        'avg_proteins': df['proteins'].mean(),
        'avg_carbs': df['carbohydrates'].mean(),
        'avg_fats': df['fats'].mean(),
        'avg_calories': df['calories'].mean(),
        'categories_list': df['category_name'].unique().tolist()
    }

    print("\nIngredient Statistics:")
    print(f"Total ingredients: {stats['total_ingredients']}")
    print(f"Number of categories: {stats['categories']}")
    print(f"Average proteins: {stats['avg_proteins']:.2f}g")
    print(f"Average carbs: {stats['avg_carbs']:.2f}g")
    print(f"Average fats: {stats['avg_fats']:.2f}g")
    print(f"Average calories: {stats['avg_calories']:.2f} kcal")
    print("\nCategories:")
    for category in stats['categories_list']:
        print(f"- {category}")

    return stats


if __name__ == "__main__":
    # Example usage
    try:
        # Get the ingredients DataFrame
        ingredients_df = get_ingredients_dataframe()

        # Get statistics
        stats = get_ingredient_stats(ingredients_df)

        # Save to CSV
        save_ingredients_to_csv(ingredients_df)

    except Exception as e:
        print(f"Error in main: {str(e)}")