
import asyncio

from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from backend.app_recipe.utils.generate_recipes import generate_recipe_variations
import os


OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_API_KEY = "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"
OPENROUTER_API_KEY = "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"
OPENROUTER_API_KEY = "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"
# BASE_MODEL_NAME = 'openai/gpt-4o'
# BASE_MODEL_NAME = 'openai/gpt-4o-mini' #'meta-llama/llama-4-maverick:free'
BASE_MODEL_NAME = 'google/gemini-2.5-flash-preview'  # 'meta-llama/llama-4-maverick:free'
MODEL_NAMES = ['openai/gpt-4o-mini', 'meta-llama/llama-4-maverick:free']
FINAL_MODEL = 'openai/gpt-4o'

if __name__ == "__main__":
    # Run the async function with parallel processing
    asyncio.run(generate_recipe_variations(batch_size=10, max_concurrent=10))
