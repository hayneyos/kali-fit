from backend.app_recipe.utils.build_receipe import build_and_store_recipes

if __name__ == "__main__":
    # Example usage
    try:
        # Build and store all recipes
        stats = build_and_store_recipes()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        print("MongoDB connection closed")
