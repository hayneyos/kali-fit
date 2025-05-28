import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
load_dotenv()
from pymongo import MongoClient

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
mongo_uri = f"mongodb://{username_quoted}:{password_quoted}@{host}:{port}/{db_name}?authSource=admin"
print(f"Connecting to MongoDB at {host}:{port}")

# MongoDB connection
try:
    client = MongoClient(mongo_uri)
    # Test the connection
    client.admin.command('ping')
    print("Successfully connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {str(e)}")
    raise

db = client['recipe_db_v3']
recipes_collection = db['recipes_v3']
gpt_recipes_collection = db['gpt_recipes']
ingredients_nutrition_collection = db['ingredients_nutrition_v3']
ingredient_categories_collection = db['ingredient_categories_v3']
ingredient_names_collection = db['ingredient_names_v3']
normalized_ingredients_collection = db['normalized_ingredients_v1']
