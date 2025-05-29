import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any
from contextlib import contextmanager

import redis
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Queue and key configurations
IMAGE_QUEUE_KEY = "image_processing_queue"
PROCESSING_QUEUE_KEY = "image_processing_in_progress"
COMPLETED_QUEUE_KEY = "image_processing_in_completed"
TASK_STATUS_KEY = "task:{}:status"
TASK_RESULT_KEY = "task:{}:result"
TASK_ERROR_KEY = "task:{}:error"
TASK_EXPIRY = 3600  # 1 hour

MAX_CONCURRENT_TASKS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
# תשתמש ברשימה לשמירת כל המשימות שנוצרו
active_tasks = set()

redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    max_connections=MAX_CONCURRENT_TASKS
)

@contextmanager
def get_redis_client():
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        client.close()

def check_redis_connection():
    try:
        with get_redis_client() as client:
            if client.ping():
                logger.info("✅ Redis connection successful")
            else:
                logger.error("❌ Redis ping failed")
    except Exception as e:
        logger.error(f"❌ Redis connection error: {e}")

async def create_openrouter_client(body: dict, image_name: str, version: str, environment: str) -> dict:
    logger.info(f"[{image_name}] Checking for mock result...")
    result_file = "mock.json"
    if os.path.exists(result_file):
        with open(result_file, "r") as f:
            return json.load(f)
    return {
        "choices": [{
            "message": {
                "content": "{\"meal_name\": \"Test Meal\", \"calories\": 500}"
            }
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300
        }
    }

async def process_image(job_id: str, body: dict, image_name: str, version: str, environment: str):
    logger.info(f"[{job_id}] 🚧 Starting image processing")
    try:
        with get_redis_client() as redis_client:
            redis_client.setex(TASK_STATUS_KEY.format(job_id), TASK_EXPIRY, "processing")

        body['model'] = "gpt-4-vision-preview"
        for field in ["email", "device_id", "ip_address", "image_name", "version"]:
            body.pop(field, None)

        max_retries, retry_delay = 3, 1
        for attempt in range(max_retries):
            try:
                response = await create_openrouter_client(body, image_name, version, environment)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        result_json = json.dumps(response)
        with get_redis_client() as redis_client:
            redis_client.setex(TASK_RESULT_KEY.format(job_id), TASK_EXPIRY, result_json)
            redis_client.setex(TASK_STATUS_KEY.format(job_id), TASK_EXPIRY, "completed")
            redis_client.rpush(COMPLETED_QUEUE_KEY, json.dumps({
                "job_id": job_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed"
            }))
        logger.info(f"[{job_id}] ✔️ Completed successfully")

    except Exception as e:
        logger.error(f"[{job_id}] ❌ Failed: {e}", exc_info=True)
        with get_redis_client() as redis_client:
            redis_client.setex(TASK_ERROR_KEY.format(job_id), TASK_EXPIRY, json.dumps({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt + 1 if 'attempt' in locals() else 1
            }))
            redis_client.setex(TASK_STATUS_KEY.format(job_id), TASK_EXPIRY, "failed")
            redis_client.rpush(COMPLETED_QUEUE_KEY, json.dumps({
                "job_id": job_id,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "status": "failed"
            }))
    finally:
        with get_redis_client() as redis_client:
            items = redis_client.lrange(PROCESSING_QUEUE_KEY, 0, -1)
            for item in items:
                try:
                    parsed = json.loads(item)
                    if parsed.get("job_id") == job_id:
                        redis_client.lrem(PROCESSING_QUEUE_KEY, 0, item)
                        break
                except json.JSONDecodeError:
                    continue

async def limited_process_image(job_id, body, image_name, version, environment):
    async with semaphore:
        await process_image(job_id, body, image_name, version, environment)

async def process_queue():
    while True:
        try:
            with get_redis_client() as redis_client:
                queue_data = redis_client.blpop(IMAGE_QUEUE_KEY, timeout=1)
                if not queue_data:
                    await asyncio.sleep(0.1)
                    continue

                _, message = queue_data
                task_data = json.loads(message)

                job_id = task_data.get('job_id')
                body = task_data.get('body', {})
                image_name = task_data.get('image_name')
                version = task_data.get('version')
                environment = task_data.get('environment')

                processing_data = {
                    "job_id": job_id,
                    "image_name": image_name,
                    "version": version,
                    "environment": environment,
                    "started_at": datetime.now(timezone.utc).isoformat()
                }
                redis_client.rpush(PROCESSING_QUEUE_KEY, json.dumps(processing_data))
                logger.info(f"[{job_id}] Moved to processing queue")

            # צור משימה שמוגבלת ע"י semaphore
            task = asyncio.create_task(limited_process_image(job_id, body, image_name, version, environment))
            active_tasks.add(task)
            task.add_done_callback(active_tasks.discard)

        except Exception as e:
            logger.error(f"❌ Error processing queue: {str(e)}", exc_info=True)
            await asyncio.sleep(1)

async def main():
    logger.info("🚀 Starting image processor service...")
    check_redis_connection()
    asyncio.create_task(process_queue())
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())