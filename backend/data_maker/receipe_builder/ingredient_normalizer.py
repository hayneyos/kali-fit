from dotenv import load_dotenv

from backend.app_recipe.utils.ingredient_normalizer import create_normalized_collection

# Load environment variables
load_dotenv()


if __name__ == "__main__":
    create_normalized_collection() 