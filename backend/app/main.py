import json
from typing import List, Optional, Dict
import uuid
import asyncio
import time
import logging
import httpx
from datetime import datetime, timezone
import threading
import os

import redis
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse
from dotenv import load_dotenv
from loguru import logger

from backend.app.queue_service import enqueue_image_analysis
# from .queue_service import enqueue_image_analysis
# from .config import settings

load_dotenv()
# Configure logging with absolute path
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'performance_test.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Initialize Redis client with connection pool
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    max_connections=10
)
redis_client = redis.Redis(connection_pool=redis_pool)

# Redis key patterns
TASK_STATUS_KEY = "task:{}:status"
TASK_RESULT_KEY = "task:{}:result"
TASK_ERROR_KEY = "task:{}:error"
TASK_EXPIRY = 3600  # 1 hour in seconds

# Request tracking
active_requests = 0
request_lock = threading.Lock()
request_history = []


def check_redis_connection():
    try:
        redis_client = redis.Redis(connection_pool=redis_pool)
        response = redis_client.ping()
        if response:
            print("✅ Redis connection successful")
        else:
            print("❌ Redis ping failed")
    except Exception as e:
        print(f"❌ Redis connection error: {e}")


def track_request(start_time):
    global active_requests
    with request_lock:
        active_requests += 1
        request_history.append({
            'start_time': start_time,
            'end_time': None,
            'duration': None
        })
        logger.info(f"Active requests: {active_requests}")


def complete_request(start_time):
    global active_requests
    with request_lock:
        active_requests -= 1
        end_time = time.time()
        duration = end_time - start_time
        request_history[-1]['end_time'] = end_time
        request_history[-1]['duration'] = duration
        logger.info(f"Request completed in {duration:.2f}s. Active requests: {active_requests}")


# Mock implementations for demonstration purposes
async def count_requests_in_db(key_type: str, key_value: str) -> int:
    """Mock database query function."""
    start_time = time.time()
    await asyncio.sleep(0.01)
    end_time = time.time()
    logger.info(f"count_requests_in_db ({key_type}): {end_time - start_time:.4f} seconds")
    return 0  # Always return 0 for testing



class MockDBService:
    """Mock database service for logging."""

    async def insert_openai_log(self, email: Optional[str], device_id: Optional[str], ip_address: str,
                                request_body: dict, response_json: dict) -> None:
        start_time = time.time()
        await asyncio.sleep(0.01)
        end_time = time.time()
        logger.info(f"insert_openai_log: {end_time - start_time:.4f} seconds")
        logger.info(f"Logging OpenAI request for email: {email}, device: {device_id}, IP: {ip_address}")

    async def create_users_table(self) -> None:
        start_time = time.time()
        await asyncio.sleep(0.01)
        end_time = time.time()
        logger.info(f"create_users_table: {end_time - start_time:.4f} seconds")

    async def upsert_user(self, email: str, device_id: Optional[str], ip_address: str) -> None:
        start_time = time.time()
        await asyncio.sleep(0.01)
        end_time = time.time()
        logger.info(f"upsert_user: {end_time - start_time:.4f} seconds")

db_service = MockDBService()


async def get_openrouter_api_key() -> str:
    return "sk-some-api-key"


app = FastAPI()

BASE_MODEL_NAME = "gpt-4-vision-preview"


@app.get("/task_status/{job_id}")
async def get_task_status(job_id: str):
    """Get the status and result of a task from Redis"""
    try:
        time.sleep(15)
        logger.info(f"[{job_id}] Checking task status")

        status = redis_client.get(TASK_STATUS_KEY.format(job_id))
        if not status:
            logger.warning(f"[{job_id}] Task not found in Redis")
            raise HTTPException(status_code=404, detail="Task not found")

        result = None
        error = None

        if status == "completed":
            logger.info(f"[{job_id}] Task completed. Retrieving result.")
            result_json = redis_client.get(TASK_RESULT_KEY.format(job_id))
            if result_json:
                result = json.loads(result_json)
                result = json.loads(result['choices'][0]['message']['content'])

        elif status == "failed":
            logger.warning(f"[{job_id}] Task failed. Retrieving error info.")
            error_json = redis_client.get(TASK_ERROR_KEY.format(job_id))
            if error_json:
                error = json.loads(error_json)

        elif status == "processing":
            logger.debug(f"[{job_id}] Task still processing. Refreshing TTL.")
            redis_client.expire(TASK_STATUS_KEY.format(job_id), TASK_EXPIRY)

        return JSONResponse(content={
            "job_id": job_id,
            "status": status,
            "result": result,
            "error": error
        })

    except redis.RedisError as e:
        logger.error(f"[{job_id}] Redis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"[{job_id}] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker container."""

    logger.info("Health check passed: Application is healthy")
    return {"status": "healthy"}



@app.post("/openai_new")
async def proxy_openai(request: Request, api_key: str = Depends(get_openrouter_api_key)):
    """Endpoint that enqueues image analysis jobs"""
    try:
        logger.info("Received /openai_new request")

        # Parse request body
        body = await request.json()
        logger.info(f"Request body: {body}")

        # Extract metadata
        image_name = body.get("image_name", "-")
        version = body.get("version", "-")
        logger.info(f"Image name: {image_name}, Version: {version}")

        # Enqueue the job
        job_id = enqueue_image_analysis(
            body=body,
            image_name=image_name,
            version=version,
            environment="prod"
        )

        logger.info(f"Job {job_id} enqueued successfully-----------------------------")

        return JSONResponse(content={
            "job_id": job_id,
            "status": "queued",
            "message": "Image analysis job has been queued"
        })

    except Exception as e:
        logger.error(f"Request error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    check_redis_connection()

    uvicorn.run(app, host='0.0.0.0', port=8000)
