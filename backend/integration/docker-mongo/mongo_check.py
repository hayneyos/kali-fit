import os
from pymongo import MongoClient
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load .env
load_dotenv()

# Get raw values
username = os.getenv("MONGO_INITDB_ROOT_USERNAME")
password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
host = os.getenv("MONGO_HOST", "localhost")
port = os.getenv("MONGO_PORT", "27017")
db = os.getenv("MONGO_DB_NAME", "admin")

# Encode credentials
username_quoted = quote_plus(username)
password_quoted = quote_plus(password)

# Build URI
mongo_uri = f"mongodb://{username_quoted}:{password_quoted}@{host}:{port}/{db}?authSource=admin"
print(mongo_uri)

try:
    client = MongoClient(mongo_uri)
    dbs = client.list_database_names()  # ✅ This is the correct method
    print("✅ MongoDB is connected.")
    print("📦 Databases:", dbs)
except Exception as e:
    print("❌ Failed to connect to MongoDB:", e)
