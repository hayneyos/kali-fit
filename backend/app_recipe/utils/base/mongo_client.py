import os
from urllib.parse import quote_plus
from pymongo import MongoClient
from datetime import datetime
# Get MongoDB credentials
username = os.getenv("MONGO_INITDB_ROOT_USERNAME")
password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
host = os.getenv("MONGO_HOST", "localhost")
port = os.getenv("MONGO_PORT", "27017")
db_name = os.getenv("MONGO_DB_NAME", "admin")

# Check if credentials are available
if not username or not password:
    raise ValueError(
        "MongoDB credentials not found. Please set MONGO_INITDB_ROOT_USERNAME and MONGO_INITDB_ROOT_PASSWORD in .env file")

# Encode credentials
username_quoted = quote_plus(str(username))
password_quoted = quote_plus(str(password))

# Build MongoDB URI
MONGO_URI = f"mongodb://{username_quoted}:{password_quoted}@{host}:{port}/{db_name}?authSource=admin"


def get_mongo_client(db_name: str = None) -> MongoClient:
    """
    Create and return a MongoDB client connection.

    Args:
        db_name (str, optional): Name of the database. If not provided, will use environment variable MONGO_DB_NAME or 'default_db'.

    Returns:
        MongoClient: MongoDB client instance
    """
    try:
        # # Get MongoDB connection details from environment variables
        # mongo_host = os.getenv('MONGO_HOST', '134.199.235.88')
        # mongo_port = int(os.getenv('MONGO_PORT', '27017'))

        if db_name is None:
            db_name = os.getenv('MONGO_DB_NAME', 'default_db')

        mongo_uri = f"mongodb://{username_quoted}:{password_quoted}@{host}:{port}/{db_name}?authSource=admin"
        client = MongoClient(mongo_uri)

        #
        # # Create MongoDB client
        # client = MongoClient(f"mongodb://{mongo_host}:{mongo_port}")
        # print(f"Connecting to MongoDB at {mongo_host}:{mongo_port}")

        # Test connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB")

        return client
    except Exception as e:
        print(f"Error connecting to MongoDB: {str(e)}")
        raise


# Initialize MongoDB client and collections
client = get_mongo_client()
db = client['recipe_db_v4']

# Collection references
recipes_v3 = db['recipes_v3']
recipes_collection = db['recipes_v3']
gpt_recipes_collection = db['gpt_recipes']
ingredients_nutrition_collection = db['ingredients_nutrition_v3']
ingredient_categories_collection = db['ingredient_categories_v3']
ingredient_names= db['ingredient_names_v3']
normalized_ingredients_collection = db['normalized_ingredients_v1']
ingredient_names_collection = db['ingredient_names_v3']