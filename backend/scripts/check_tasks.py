import redis
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Redis key patterns
TASK_STATUS_KEY = "task:{}:status"
TASK_RESULT_KEY = "task:{}:result"
TASK_ERROR_KEY = "task:{}:error"
IMAGE_QUEUE_KEY = "image_processing_queue"
PROCESSING_QUEUE_KEY = "processing_queue"

def connect_to_redis():
    """Create Redis connection"""
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        logger.info("✅ Successfully connected to Redis")
        return redis_client
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        return None

def get_task_info(redis_client, task_id):
    """Get all information about a task"""
    try:
        # Get status
        status = redis_client.get(TASK_STATUS_KEY.format(task_id))
        if not status:
            logger.warning(f"❌ Task {task_id} not found")
            return None

        # Get result or error based on status
        result = None
        error = None
        
        if status == "completed":
            result_json = redis_client.get(TASK_RESULT_KEY.format(task_id))
            if result_json:
                result = json.loads(result_json)
        elif status == "failed":
            error_json = redis_client.get(TASK_ERROR_KEY.format(task_id))
            if error_json:
                error = json.loads(error_json)

        # Get TTL (Time To Live) for each key
        status_ttl = redis_client.ttl(TASK_STATUS_KEY.format(task_id))
        result_ttl = redis_client.ttl(TASK_RESULT_KEY.format(task_id))
        error_ttl = redis_client.ttl(TASK_ERROR_KEY.format(task_id))

        return {
            "task_id": task_id,
            "status": status,
            "result": result,
            "error": error,
            "ttl": {
                "status": status_ttl,
                "result": result_ttl,
                "error": error_ttl
            }
        }
    except Exception as e:
        logger.error(f"❌ Error getting task info: {e}")
        return None

def list_all_tasks(redis_client):
    """List all tasks in Redis"""
    try:
        # Get all keys matching the status pattern
        status_keys = redis_client.keys("task:*:status")
        tasks = []
        
        for key in status_keys:
            # Extract task_id from key
            task_id = key.split(":")[1]
            task_info = get_task_info(redis_client, task_id)
            if task_info:
                tasks.append(task_info)
        
        return tasks
    except Exception as e:
        logger.error(f"❌ Error listing tasks: {e}")
        return []

def check_queue(redis_client):
    """Check the image processing queue"""
    try:
        # Check main queue
        queue_length = redis_client.llen(IMAGE_QUEUE_KEY)
        if queue_length > 0:
            logger.info(f"\nFound {queue_length} items in the main queue: {IMAGE_QUEUE_KEY}")
            # Get all items in queue
            queue_items = redis_client.lrange(IMAGE_QUEUE_KEY, 0, -1)
            for item in queue_items:
                try:
                    task_data = json.loads(item)
                    logger.info(f"Queue item: {json.dumps(task_data, indent=2)}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in queue: {item}")
        else:
            logger.info("\nMain queue is empty")

        # Check processing queue
        processing_length = redis_client.llen(PROCESSING_QUEUE_KEY)
        if processing_length > 0:
            logger.info(f"\nFound {processing_length} items in the processing queue: {PROCESSING_QUEUE_KEY}")
            # Get all items in processing queue
            processing_items = redis_client.lrange(PROCESSING_QUEUE_KEY, 0, -1)
            for item in processing_items:
                try:
                    task_data = json.loads(item)
                    logger.info(f"Processing item: {json.dumps(task_data, indent=2)}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in processing queue: {item}")
        else:
            logger.info("\nProcessing queue is empty")
    except Exception as e:
        logger.error(f"❌ Error checking queues: {e}")

def print_task_info(task_info):
    """Pretty print task information"""
    if not task_info:
        return
    
    logger.info("\n" + "="*50)
    logger.info(f"Task ID: {task_info['task_id']}")
    logger.info(f"Status: {task_info['status']}")
    
    if task_info['result']:
        logger.info("\nResult:")
        logger.info(json.dumps(task_info['result'], indent=2))
    
    if task_info['error']:
        logger.info("\nError:")
        logger.info(json.dumps(task_info['error'], indent=2))
    
    logger.info("\nTTL (seconds until expiration):")
    logger.info(f"Status: {task_info['ttl']['status']}")
    logger.info(f"Result: {task_info['ttl']['result']}")
    logger.info(f"Error: {task_info['ttl']['error']}")
    logger.info("="*50 + "\n")

def clear_tasks(redis_client):
    """Clear all tasks from Redis"""
    try:
        # Get all keys matching any task pattern
        all_keys = redis_client.keys("task:*")
        if all_keys:
            redis_client.delete(*all_keys)
            logger.info(f"✅ Successfully cleared {len(all_keys)} task keys")
        else:
            logger.info("ℹ️ No tasks found to clear")
            
        # Clear queues
        redis_client.delete(IMAGE_QUEUE_KEY)
        redis_client.delete(PROCESSING_QUEUE_KEY)
        logger.info("✅ Cleared all queues")
    except Exception as e:
        logger.error(f"❌ Error clearing tasks: {e}")

def main():
    # Configure logger
    logger.add("task_checker.log", rotation="1 day")
    # Connect to Redis
    redis_client = connect_to_redis()
    if not redis_client:
        return
    clear_tasks(redis_client)

    # Check queue first
    logger.info("\nChecking image processing queue...")
    check_queue(redis_client)

    # List all tasks
    logger.info("\nListing all tasks...")
    tasks = list_all_tasks(redis_client)
    if tasks:
        logger.info(f"\nFound {len(tasks)} tasks:")
        for task in tasks:
            print_task_info(task)
    else:
        logger.info("No tasks found")

if __name__ == "__main__":
    main() 