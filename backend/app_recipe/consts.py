import os

from backend.app_recipe.config import settings

LOCAL_PORT = 8074

WHATSAPP_API_URL = "https://graph.facebook.com/v22.0/{phone_number_id}/messages"
ACCESS_TOKEN = settings.ACCESS_TOKEN
PHONE_NUMBER_ID = settings.PHONE_NUMBER_ID
VERIFY_TOKEN = settings.VERIFY_TOKEN

UPLOAD_FOLDER = f"{settings.DATA_DIR}/uploads"
UPLOAD_FOLDER_WEB = f"{settings.DATA_DIR}/uploads/web"
UPLOAD_FOLDER_APP = f"{settings.DATA_DIR}/uploads/app"
UPLOAD_FOLDER_APP = f"{settings.DATA_DIR}/uploads/app"
RECIPE_FOLDER_APP = f"{settings.DATA_DIR}/uploads/recipe"

UPLOAD_FOLDER_CHEN_APP = f"/home/data/chendesign/images/"
BASE_MODEL_NAME = 'google/gemini-2.5-flash-preview'  # 'meta-llama/llama-4-maverick:free'
BASE_MODEL_MINI_NAME = 'openai/gpt-4o-mini'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_WEB, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_APP, exist_ok=True)