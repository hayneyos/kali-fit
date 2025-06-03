import pandas as pd
import pandas as pd
from typing import Dict, List, Optional
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

from backend.app_recipe.utils.base.mongo_client import normalized_ingredients_collection, ingredient_names_collection, \
    ingredients_nutrition_collection, ingredient_categories_collection

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
        category_name = doc.get('category_name','')
        category_id = doc.get('category_id', '')
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
                'primary_name' : doc.get('primary_name'),
                'category_name' :doc.get('category_name'),
                'category_id' : doc.get('category_id'),
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
                'primary_name' : primary_name,
                'category_name' : category_name,
                'category_id' : category_id,
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
    Get ingredient data by merging ingredient_names_v3, ingredients_nutrition_v3, and ingredient_categories_v3 collections.

    Returns:
        pd.DataFrame: Merged ingredient data with nutrition and category information
    """
    try:
        # Get all documents from all collections
        names_data = list(ingredient_names_collection.find({}))
        nutrition_data = list(ingredients_nutrition_collection.find({}))
        categories_data = list(ingredient_categories_collection.find({}))

        # Create DataFrames
        names_df = pd.DataFrame(names_data)
        nutrition_df = pd.DataFrame(nutrition_data)
        categories_df = pd.DataFrame(categories_data)

        print("\nNames DataFrame columns:", names_df.columns.tolist())
        print("\nNutrition DataFrame columns:", nutrition_df.columns.tolist())
        print("\nCategories DataFrame columns:", categories_df.columns.tolist())

        # Merge names and nutrition on nutrition_id
        merged_df = pd.merge(
            names_df,
            nutrition_df,
            left_on='nutrition_id',
            right_on='_id',
            how='left',
            suffixes=('_names', '_nutrition')
        )

        # Ensure category_id is present for the next merge
        if 'category_id_x' in merged_df.columns:
            merged_df['category_id'] = merged_df['category_id_x']
        elif 'category_id' not in merged_df.columns and 'category_id_y' in merged_df.columns:
            merged_df['category_id'] = merged_df['category_id_y']

        # # Merge with categories on category_id
        # merged_df = pd.merge(
        #     merged_df,
        #     categories_df[['name', '_id']],
        #     left_on='category_id_names',
        #     right_on='_id',
        #     how='left',
        #     suffixes=('', '_category')
        # )

        # Rename the category name column for clarity
        # merged_df = merged_df.rename(columns={'name': 'category_name'})

        # Select and rename columns
        columns_to_keep = {
            '_id_names': 'names_id',
            '_id_nutrition': 'nutrition_id',
            'category_id': 'category_id',
            'category_name': 'category_name',
            'primary_name': 'primary_name',
            'language': 'language',
            'form': 'form',
            'name': 'name',
            'synonyms': 'synonyms',
            'possible_measurement': 'possible_measurement',
            'base_ingredient_name': 'base_ingredient_name',
            'average_weight': 'average_weight',
            'data_sources': 'data_sources',
            'created_at': 'created_at',
            'last_updated': 'last_updated'
        }

        # Check which columns exist in the DataFrame
        existing_columns = [col for col in columns_to_keep.keys() if col in merged_df.columns]
        if not existing_columns:
            raise ValueError("No matching columns found in DataFrame")

        # Create final DataFrame with only existing columns
        final_df = merged_df[existing_columns].rename(columns=columns_to_keep)

        # Extract nutrition data from data_sources
        def extract_latest_nutrition(data_sources):
            if not data_sources or not isinstance(data_sources, list):
                return pd.Series({
                    'proteins_per_100g': None,
                    'carbohydrates_per_100g': None,
                    'fats_per_100g': None,
                    'calories_per_100g': None,
                    'source': None
                })
            # Get the latest data source
            latest_source = max(data_sources, key=lambda x: x.get('last_updated', datetime.min))
            return pd.Series({
                'proteins_per_100g': latest_source.get('proteins_per_100g'),
                'carbohydrates_per_100g': latest_source.get('carbohydrates_per_100g'),
                'fats_per_100g': latest_source.get('fats_per_100g'),
                'calories_per_100g': latest_source.get('calories_per_100g'),
                'source': latest_source.get('source')
            })

        # Apply the extraction function
        nutrition_data = final_df['data_sources'].apply(extract_latest_nutrition)
        final_df = pd.concat([final_df, nutrition_data], axis=1)

        # Convert numeric columns
        numeric_columns = [
            'proteins_per_100g',
            'carbohydrates_per_100g',
            'fats_per_100g',
            'calories_per_100g'
        ]
        for col in numeric_columns:
            if col in final_df.columns:
                final_df[col] = pd.to_numeric(
                    final_df[col].astype(str).str.replace('g', '').str.replace('kcal', ''),
                    errors='coerce'
                )

        # Sort by ingredient name and language
        final_df = final_df.sort_values(['primary_name', 'language'])

        print(f"\nCreated DataFrame with {len(final_df)} ingredient entries")
        print("\nColumns in the final DataFrame:")
        print(final_df.columns.tolist())
        print("\nSample of the data:")
        print(final_df.head())

        return final_df

    except Exception as e:
        print(f"Error creating ingredients DataFrame: {str(e)}")
        print("\nDebug information:")
        print(f"Number of name records: {len(names_data)}")
        print(f"Number of nutrition records: {len(nutrition_data)}")
        print(f"Number of category records: {len(categories_data)}")
        raise
    finally:
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
#
#
# if __name__ == "__main__":
#     # Example usage
#     try:
#         # Get the ingredients DataFrame
#         ingredients_df = get_ingredients_dataframe()
#
#         # Get statistics
#         stats = get_ingredient_stats(ingredients_df)
#
#         # Save to CSV
#         save_ingredients_to_csv(ingredients_df)
#
#     except Exception as e:
#         print(f"Error in main: {str(e)}")