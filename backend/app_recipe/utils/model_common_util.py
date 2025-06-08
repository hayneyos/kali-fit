import base64
import io
import os
import json
from typing import List, Dict, Tuple
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv
from pymongo import MongoClient
from urllib.parse import quote_plus
from datetime import datetime
import asyncio
import requests
import time


OPENAI_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OPENROUTER_API_KEY = "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"
# OPENROUTER_API_KEY = "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"
OPENROUTER_API_KEY = "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"

async def execute_call(body, model, file_name="", image_path="", version="v1", environment="prod", prompt_id=1):
    start_time = time.time()  # Start timing

    # Extract image details from body before API call
    image_details = extract_image_details_from_body(body)

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json'
            },
            json=body,
            timeout=60
        )

    except Exception as e:
        print(f"Error in API call: {str(e)}")
        response = {}

    return response


def extract_image_details_from_body(body):
    """Extract image details from the request body"""
    image_details = {}
    try:
        # Find image URL in the body
        for message in body.get('messages', []):
            if isinstance(message.get('content'), list):
                for content in message['content']:
                    if content.get('type') == 'image_url':
                        image_url = content.get('image_url', {}).get('url', '')
                        if image_url.startswith('data:image'):
                            # Process base64 image
                            image_details = process_single_image(image_url, is_base64=True)
                        elif image_url.startswith('file://'):
                            # Process file image
                            file_path = image_url[7:]  # Remove 'file://'
                            image_details = process_single_image(file_path, is_base64=False)
                        else:
                            # Handle URL
                            image_details = {
                                'source_type': 'url',
                                'url': image_url
                            }
    except Exception as e:
        print(f"Error extracting image details from body: {str(e)}")

    return image_details


def process_single_image(image_data, is_base64=True):
    """Process a single image and return its details"""
    try:
        if is_base64:
            # Handle base64 image
            image_data = base64.b64decode(image_data.split(',')[1])
            source_type = 'base64'
        else:
            # Handle file path
            source_type = 'file'

        with Image.open(io.BytesIO(image_data) if is_base64 else image_data) as img:
            # Get basic image info
            basic_info = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': len(image_data) if is_base64 else os.path.getsize(image_data),
                'aspect_ratio': round(img.width / img.height, 3),
                'orientation': 'landscape' if img.width > img.height else 'portrait' if img.height > img.width else 'square',
                'source_type': source_type,
                'processing_time': time.time()  # Add timestamp for tracking
            }

            # Get other image info
            other_info = {}
            try:
                for key, value in img.info.items():
                    try:
                        other_info[key] = _convert_to_serializable(value)
                    except Exception as e:
                        print(f"Warning: Could not process image info {key}: {str(e)}")
                        continue
            except Exception as e:
                print(f"Warning: Could not process image info: {str(e)}")

            # Combine all info
            return _convert_to_serializable({
                **basic_info,
                'image_info': other_info
            })

    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None



def _convert_to_serializable(value):
    """Convert non-JSON serializable values to strings or remove them"""
    try:
        if value is None:
            return None
        elif isinstance(value, (int, float, str, bool)):
            return value
        elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):  # Handle IFDRational
            return f"{value.numerator}/{value.denominator}"
        elif isinstance(value, (tuple, list)):
            return [_convert_to_serializable(item) for item in value]
        elif isinstance(value, dict):
            return {str(k): _convert_to_serializable(v) for k, v in value.items()}
        elif hasattr(value, '__dict__'):  # Handle objects with __dict__
            return _convert_to_serializable(value.__dict__)
        elif hasattr(value, 'isoformat'):  # Handle datetime objects
            return value.isoformat()
        elif hasattr(value, 'hex'):  # Handle bytes
            return value.hex()
        else:
            return str(value)
    except Exception as e:
        print(f"Warning: Could not convert value {value} to serializable format: {str(e)}")
        return str(value)

