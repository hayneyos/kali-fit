from dotenv import load_dotenv

# Load environment variables
load_dotenv()


from backend.app_recipe.utils.ingredient_utils import get_ingredient_stats, save_ingredients_to_csv, \
    get_ingredients_dataframe
from backend.app_recipe.utils.mongo_handler_utils import *

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
