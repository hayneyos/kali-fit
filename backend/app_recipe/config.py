import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import field_validator
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    # Server Configuration
    MY_SERVER_IP: str
    MY_SERVER_NAME: str
    RUNNING_IN_DOCKER: bool = False
    USE_API_PREFIX: bool = False

    # Data Configuration
    DATA_DIR: str = "/home/data/kaila/"
    LOG_DIR: str = "/home/data/kaila/logs"

    # API Configuration
    API_PREFIX: str = "/api"
    ALLOWED_ORIGINS: List[str] = []

    # WhatsApp Configuration
    ACCESS_TOKEN: str
    PHONE_NUMBER_ID: str
    VERIFY_TOKEN: str

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database Configuration
    DATABASE_URL: str

    # Stripe Configuration
    STRIPE_SECRET_KEY: str
    PRICE_ID: str

    # OpenAI Configuration
    OPENROUTER_API_KEY: str
    PINESCRIPT_OPENROUTER_MODEL: str

    # Survey Configuration
    SURVEY_URL: str

    # Email Configuration
    MAIL_USERNAME: str
    MAIL_PASSWORD: str

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_origins(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @field_validator("RUNNING_IN_DOCKER", "USE_API_PREFIX", mode="before")
    @classmethod
    def convert_to_bool(cls, v: str) -> bool:
        if isinstance(v, str):
            return v.lower() == "true"
        return v

    model_config = SettingsConfigDict(
        env_file=env_path,
        case_sensitive=True,
        extra="allow"  # Allow extra fields in the .env file
    )

# Create settings instance
settings = Settings()

# Validate required directories
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)