import logging
import os
import pandas as pd

from starlette.responses import FileResponse, JSONResponse
from backend.app_recipe.consts import RECIPE_FOLDER_APP, UPLOAD_FOLDER_APP
from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends
from backend.app_recipe.utils.ingredient_utils import get_ingredients_dataframe

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('wizard_routes')

# Load environment variables
router = APIRouter()


# Cache for ingredients DataFrame
_ingredients_df_cache = None
name_to_english_cache = None  # Cache for the name-to-english mapping

@router.get("/uploads/{filename}/{directory}")
async def uploaded_file(filename: str, directory: str = ""):
    if directory and directory.find("recipe")>=0:
        file_path = os.path.join(RECIPE_FOLDER_APP, filename)
    else:
        file_path = os.path.join(UPLOAD_FOLDER_APP, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), directory: str = File(default="")):
    try:
        # Determine the target directory
        target_dir = RECIPE_FOLDER_APP if directory and  directory.find("recipe")>=0 else UPLOAD_FOLDER_APP
        
        # Create upload directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)

        # Save the file
        file_path = os.path.join(target_dir, file.filename)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        return {"filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

@router.get("/find_ingredient_by_name")
async def find_ingredient_by_name(
        query: str,
        lang: str,
        request: Request = None
):
    try:
        # Log the incoming request
        logger.info(f"Finding ingredient for query: {query} in language: {lang}")

        # Get the DataFrame from cache
        df = get_cached_ingredients_dataframe()

        # Define language mapping
        language_mapping = {
            'en': 'english',
            'ru': 'russian',
            'es': 'spanish',
            'he': 'hebrew'
        }

        # Convert short language code to full name
        full_lang = language_mapping.get(lang.lower())
        if not full_lang:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported language: {lang}. Supported languages are: {', '.join(language_mapping.keys())}"
            )

        # Define language column mappings for the new structure
        lang_columns = {
            'english': ['name', 'synonyms'],
            'russian': ['name', 'synonyms'],
            'spanish': ['name', 'synonyms'],
            'hebrew': ['name', 'synonyms']
        }

        # Filter DataFrame for the requested language
        lang_df = df[df['language'] == full_lang]

        # Handle empty query
        if not query or query.strip() == "":
            return JSONResponse(content={"results": []})

        # Create a mask for name and synonyms
        name_mask = lang_df['name'].str.lower().str.contains(query.lower(), na=False)

        # Combine masks with OR operation
        final_mask = name_mask

        # Filter the DataFrame
        filtered_df = lang_df[final_mask]

        # Select and rename columns for the response
        response_columns = {
            'primary_name': 'primary_name',
            'name': f'{lang}_name',
            'category_id': 'category_id',
            'form': 'form',
            'proteins_per_100g': 'proteins_per_100g',
            'carbohydrates_per_100g': 'carbohydrates_per_100g',
            'fats_per_100g': 'fats_per_100g',
            'calories_per_100g': 'calories_per_100g',
            'source': 'source',
            'possible_measurement': 'possible_measurement',
            'average_weight': 'average_weight'
        }

        # Select only existing columns
        existing_columns = [col for col in response_columns.keys() if col in filtered_df.columns]
        filtered_df = filtered_df[existing_columns].rename(columns=response_columns)

        # Convert numeric columns to string with units and set default if None
        for col in ['proteins_per_100g', 'carbohydrates_per_100g', 'fats_per_100g']:
            if col in filtered_df.columns:
                filtered_df[col] = filtered_df[col].apply(lambda x: f"{x}g" if pd.notnull(x) and x != '' else "1g")

        if 'calories_per_100g' in filtered_df.columns:
            filtered_df['calories_per_100g'] = filtered_df['calories_per_100g'].apply(lambda x: f"{x}kcal" if pd.notnull(x) and x != '' else "1kcal")

        # Set default form value
        filtered_df['form'] = "-"
        filtered_df['synonyms_str'] = "-"
        filtered_df['data_source'] = "-"

        # Convert list fields to strings for deduplication
        list_columns = ['possible_measurement', 'synonyms']
        for col in list_columns:
            if col in filtered_df.columns:
                filtered_df[col] = filtered_df[col].apply(
                    lambda x: ','.join(sorted(x)) if isinstance(x, list) else str(x)
                )

        print('before drop')
        filtered_df.drop_duplicates(inplace=True)

        # Add match_type: 0 for exact, 1+ for other matches based on position
        def match_type_func(x):
            x_lower = x.lower()
            q_lower = query.lower()
            if x_lower == q_lower:
                return 0
            else:
                # Find the position of the query in the string
                pos = x_lower.find(q_lower)
                if pos == -1:  # Should not happen due to the mask, but just in case
                    return 999
                # Return position + 1 (so it's always > 0)
                return pos + 1
        filtered_df['match_type'] = filtered_df['primary_name'].apply(match_type_func)

        # Sort by match type (exact first, then by position), then by the name column (ABC)
        filtered_df = filtered_df.sort_values(['match_type', 'primary_name'])

        # Remove the temporary sorting column
        filtered_df = filtered_df.drop('match_type', axis=1)

        results = filtered_df.to_dict('records')

        return JSONResponse(content={"results": results})

    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = f"Error finding ingredient: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
