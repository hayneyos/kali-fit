import asyncio
import sys
import os

from dotenv import load_dotenv


# Load environment variables
load_dotenv()

from backend.app_recipe.utils.base.mongo_client import recipes_collection, gpt_recipes_collection  # or your actual collection import


# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app_recipe.utils.generate_recipes import get_random_recipe_sample, generate_recipe_variations, process_recipe_batch

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

def recipe_exists(original_recipe_name):
    return gpt_recipes_collection.find_one({"original_recipe_name": original_recipe_name}) is not None

async def main():
    try:
        # Get a random sample of 1000 recipes
        print("Starting to sample 1000 random recipes...")
        sample_recipes = get_random_recipe_sample(500)
        
        if not sample_recipes:
            print("Failed to get recipe sample. Exiting...")
            return

        print(f"Successfully sampled {len(sample_recipes)} recipes")
        print("Starting recipe variation generation...")
        
        # Process recipes in batches
        batch_size = 10
        total_processed = 0
        total_successful = 0
        
        for i in range(0, len(sample_recipes), batch_size):
            batch = sample_recipes[i:i + batch_size]
            # Filter out recipes that already exist in gpt_recipes_collection by original_recipe_name
            batch_to_process = [r for r in batch if not recipe_exists(r['title'])]
            print(f"\nProcessing batch {i//batch_size + 1} of {(len(sample_recipes) + batch_size - 1)//batch_size}")
            print(f"Recipes to process in this batch (after existence check): {len(batch_to_process)}")

            if not batch_to_process:
                print("All recipes in this batch already exist. Skipping.")
                continue

            # Process the batch
            processed, successful = await process_recipe_batch(batch_to_process, BASE_MODEL_NAME)
            
            total_processed += processed
            total_successful += successful
            
            print(f"Batch progress: {processed} processed, {successful} successful")
            print(f"Overall progress: {total_processed}/{len(sample_recipes)} recipes processed")
            print(f"Overall success rate: {(total_successful/total_processed)*100:.2f}%")
            
            # Add a small delay between batches to avoid rate limits
            await asyncio.sleep(2)
        
        print("\nRecipe generation completed successfully!")
        print(f"Final statistics:")
        print(f"Total recipes processed: {total_processed}")
        print(f"Successfully generated variations: {total_successful}")
        print(f"Overall success rate: {(total_successful/total_processed)*100:.2f}%")
        
    except Exception as e:
        print(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 