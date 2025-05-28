import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Base directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    
    # Upload directory for images
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    
    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", None)
    
    # Queue settings
    IMAGE_QUEUE_KEY: str = "image_processing_queue"
    TASK_STATUS_KEY: str = "task_status:{}"
    TASK_RESULT_KEY: str = "task_result:{}"
    TASK_ERROR_KEY: str = "task_error:{}"
    TASK_EXPIRY: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"

# Create settings instance
settings = Settings()

# Ensure upload directory exists
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True) 