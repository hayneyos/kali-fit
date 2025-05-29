import os
import sys

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

# Set environment variables
os.environ.update({
    # Server settings
    "SERVER_HOST": "0.0.0.0",
    "SERVER_PORT": "8091",
    
    # Directory settings
    "LOG_DIR": "logs",
    "DATA_DIR": "data",
    "UPLOAD_FOLDER_APP": "static/uploads",
    
    # Server info
    "MY_SERVER_IP": "localhost",
    "MY_SERVER_NAME": "localhost",
    "RUNNING_IN_DOCKER": "false",
    "USE_API_PREFIX": "false",
    
    # MongoDB settings
    "MONGO_HOST": "134.199.235.88",
    "MONGO_PORT": "27017",
    "MONGO_USERNAME": "admin",
    "MONGO_PASSWORD": "road0247!~Sense!@#$",
    "MONGO_DB_NAME": "mydatabase",
    
    # Redis settings
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "",
    
    # API settings
    "OPENROUTER_API_KEY": "sk-or-v1-f263eb818e717dd...a805effec4e2216eda26fc3",
    "OPENROUTER_MODEL": "openai/gpt-4o-mini"
})

# Create required directories
os.makedirs(os.environ["LOG_DIR"], exist_ok=True)
os.makedirs(os.environ["DATA_DIR"], exist_ok=True)
os.makedirs(os.environ["UPLOAD_FOLDER_APP"], exist_ok=True)

# Import and run the application
from main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv('SERVER_HOST', '0.0.0.0'),
        port=int(os.getenv('SERVER_PORT', 8091)),
        loop="uvloop",
        limit_concurrency=1000,
        backlog=2048,
        workers=1,
        reload=False
    ) 