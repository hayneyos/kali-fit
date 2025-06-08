import base64
import io
import json
import logging
import os
import time
import base64
from PIL import Image
import io
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Depends

from backend.app_recipe.utils.model_common_util import execute_call

VALIDATION_MODEL_PROD = """
  As a professional nutritionist, analyze the provided food image and return accurate nutritional data in strict JSON format.

ANALYSIS INSTRUCTIONS:

1. IDENTIFY ALL VISIBLE ITEMS:
   - Include partially hidden items, sauces, and items extending beyond the frame
   - Identify the likely cuisine type (e.g., Mediterranean, Asian, American)
   - Account for perspective distortion and lighting variations when estimating size/quantity

2. ESTIMATE QUANTITIES (WITH IMAGE GEOMETRY AND CAMERA ANGLE):
    - Use known reference objects in the image (e.g. standard fork ≈ 18cm, plate ≈ 27cm diameter) to scale food items
    - Adjust estimates based on camera angle:
       * If taken from top-down (90°) – use area coverage on plate for volume approximation
       * If taken from ~45° – apply foreshortening correction to infer height/depth
       * If taken from low angle (<30°) – estimate vertical volume more accurately but adjust for occlusion
    - Document:
       * Apparent scaling ratios
       * Any overlap, stacking, or visual distortion that affects estimation
    - Provide comparison-based estimates such as:
       * "Meat portion ≈ 2× fork length in width, 1× in thickness"
       * "Rice occupies ⅓ of the plate area, thickness ~1.5 cm"

3. PROVIDE COMPLETE NUTRITIONAL BREAKDOWN:
   - Calculate: proteins, carbohydrates, fats in grams
   - Sum total calories: (proteins × 4) + (carbs × 4) + (fats × 9)
   - Include likely ingredients used in preparation (oils, spices) when evident
   - Use USDA FoodData Central or equivalent databases

4. DOCUMENT ALL ASSUMPTIONS:
   - Size comparisons used
   - Inferences based on shape, shadow, overlap
   - Perspective adjustments made
   - Preparation method assumptions

Return output in this JSON format:

  "output_format": {
    "meal_name": "Descriptive name of the combined meal",
    "cuisine_type": "Mediterranean/Asian/etc.",
    "estimated_calories": "number",
    "macronutrients": {
      "proteins": "string (e.g., 'Xg')",
      "carbohydrates": "string (e.g., 'Xg')",
      "fats": "string (e.g., 'Xg')"
    },
    "estimated_weight": "string (e.g., 'Total grams')",
    "weight_estimation_details": "array of strings" -> example ,[
        "4 Ribeye steaks × 300g = 1200g",
        "2 T-bone steaks × 300g = 600g"
      ],
    "ingredients": "array of strings",
    "cooking_state": "string ('raw' or 'cooked' or 'unknown')",
    "category": "string ('vegetarian' or 'meat (poultry)' or 'meat (beef/lamb/pork)' or 'fish/seafood' or 'partially meat')",
    "category_cause": "string",
    "assumptions": "array of strings",
    "part_identification_confidence": "object (key: string (cut name), value: string (percentage))",
    "health_assessment": "string",
    "source": "string (e.g., 'USDA FoodData Central')",
    "confidence_level": "string ('low' or 'medium' or 'high')",
    "macronutrients_by_ingredient": "object (key: string (ingredient name), value: object { 'proteins': 'string', 'carbohydrates': 'string', 'fats': 'string', 'calories': 'string' })",
    "judge": {
      "final_meal_name": "string",
      "estimated_total_calories": "number",
      "total_macronutrients": {
        "protein_grams": "number",
        "fat_grams": "number",
        "carbohydrate_grams": "number"
      },
      "final_ingredients_list": "array of strings",
      "final_assumptions": "array of strings",
      "cooking_state": "string ('raw' or 'cooked' or 'unknown')",
      "category": "string",
      "category_cause": "string",
      "source": "string",
      "judge_estimation_calories": {
        "total_estimated_calories": "number",
        "ingredient_breakdown": "array of objects (each object: { 'ingredient': 'string', 'estimated_weight_grams': 'number', 'estimated_kcal_per_gram': 'number', 'estimated_calories': 'number', 'weight_estimation_steps': 'array of strings', 'macronutrients': { 'protein_grams': 'number', 'fat_grams': 'number', 'carbohydrate_grams': 'number' } })",
        "calculation_method": "string"
      }
    }
  }


🚩 Return only a valid JSON block.  
🚩 Do not include markdown, explanations, or additional text.  
🚩 This is your final expert-level output for visual nutritional analysis.
"""


def get_openrouter_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="API key not configured")
    return key


def process_image(image_path, max_size=(512, 512), logger=None):
    """Process image and return base64 encoded data along with detailed image information"""
    try:
        # Load image
        with Image.open(image_path) as img:
            # Get original image details
            original_details = {
                'size': img.size,  # (width, height)
                'format': img.format,
                'mode': img.mode,
                'dpi': img.info.get('dpi', None),
                'compression': img.info.get('compression', None),
                'progressive': img.info.get('progressive', False),
                'transparency': img.info.get('transparency', None),
                'file_size': os.path.getsize(image_path),
                'aspect_ratio': round(img.size[0] / img.size[1], 3),
                'orientation': 'landscape' if img.size[0] > img.size[1] else 'portrait' if img.size[1] > img.size[
                    0] else 'square'
            }

            # Resize image (preserve aspect ratio)
            img.thumbnail(max_size)
            resized_details = {
                'size': img.size,
                'aspect_ratio': round(img.size[0] / img.size[1], 3),
                'orientation': 'landscape' if img.size[0] > img.size[1] else 'portrait' if img.size[1] > img.size[
                    0] else 'square'
            }

            # Save to memory buffer
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=95)
            buffered_size = len(buffered.getvalue())

            # Encode to base64
            encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Combine all details
            image_details = {
                'original': original_details,
                'resized': resized_details,
                'processing': {
                    'max_dimension': max_size[0],
                    'quality': 95,
                    'format': 'JPEG',
                    'encoded_size': len(encoded),
                    'compression_ratio': round(buffered_size / original_details['file_size'], 3)
                }
            }

            return {
                'base64': encoded,
                'details': image_details
            }

    except Exception as e:
        if logger != None:
            logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")


def generate_validation_prompt(final_result_dict):
    return VALIDATION_MODEL_PROD


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


async def create_openrouter_client_for_meals(body_dima, image_name="", version="v1", environment="prod", prompt_id=1):
    try:
        text = generate_validation_prompt({})
    except Exception as e:
        text = ""

    try:
        # Extract image URL from the body
        image_url = body_dima.get('messages', [{}])[0].get('content', [{}])[1].get('image_url', {}).get('url', "")

        # Process image if it's a local file
        if image_url and len(image_url) < 250:
            image_url = image_url.replace("https://for-checking.live/api/uploads/", "/home/data/kaila/uploads/app/")
            # Process image and get details
            encode_data = encode_image(image_url)
            image_url = f"data:image/jpeg;base64,{encode_data}"
            # {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_data}"}},
            # image_url, image_details = process_image(image_url)

            # Create image details object
            # image_details['source_type'] = 'local'
        else:
            image_details = {
                'source_type': 'url',
                'url': image_url
            }
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        image_url = ""
        image_details = {}

    model = body_dima['model']

    content = []

    if text:
        content.append({
            "type": "text",
            "text": text
        })

    if image_url:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url
            }
        })

    # if content is empty - must raise error, not send empty request
    if not content:
        raise ValueError("No valid content (text or image_url) found to send to OpenRouter.")

    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }

    # print(json.dumps(body, indent=2))  # Debug print

    # Add image details to the body for later extraction
    # body['image_details'] = image_details

    try:
        response = await execute_call(body, model, file_name=image_name, image_path=image_name, version=version,
                                      environment=environment, prompt_id=prompt_id)
    except Exception as exp:
        print(exp)
    return response

