import json
import uuid
from typing import Dict, Any, Optional
from contextlib import contextmanager

import redis
from loguru import logger

from .config import settings

# Initialize Redis connection pool
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
    max_connections=10
)

@contextmanager
def get_redis_client():
    """Context manager for Redis client to ensure proper connection handling"""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        client.close()

def enqueue_image_analysis(body: Dict[str, Any], image_name: str, version: str, environment: str) -> str:
    """
    Enqueue an image analysis job and return the job ID
    """
    job_id = str(uuid.uuid4())
    
    task_data = {
        "job_id": job_id,
        "body": body,
        "image_name": image_name,
        "version": version,
        "environment": environment
    }
    
    with get_redis_client() as redis_client:
        # Add task to queue
        redis_client.rpush(settings.IMAGE_QUEUE_KEY, json.dumps(task_data))
        # Set initial status
        redis_client.setex(settings.TASK_STATUS_KEY.format(job_id), settings.TASK_EXPIRY, "queued")
        
    logger.info(f"Job {job_id} enqueued for image {image_name}")
    return job_id

def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the current status and result of a job
    """
    with get_redis_client() as redis_client:
        status = redis_client.get(settings.TASK_STATUS_KEY.format(job_id))
        
        if not status:
            return {"status": "not_found", "error": "Job not found"}
            
        result = {
            "status": status,
            "job_id": job_id
        }
        
        if status == "completed":
            result_data = redis_client.get(settings.TASK_RESULT_KEY.format(job_id))
            if result_data:
                result["result"] = json.loads(result_data)
                
        elif status == "failed":
            error_data = redis_client.get(settings.TASK_ERROR_KEY.format(job_id))
            if error_data:
                result["error"] = json.loads(error_data)
                
        return result

def wait_for_job_completion(job_id: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Wait for a job to complete and return its result
    timeout: maximum time to wait in seconds
    """
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        status = get_job_status(job_id)
        
        if status["status"] in ["completed", "failed"]:
            return status
            
        time.sleep(1)  # Wait 1 second before checking again
        
    return {
        "status": "timeout",
        "error": "Job processing timed out",
        "job_id": job_id
    } 