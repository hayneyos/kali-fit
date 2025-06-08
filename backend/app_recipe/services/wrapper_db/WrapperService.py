from backend.app_recipe.services.wrapper_db.MyDbPostgresService import MyDbPostgresService
import asyncio
import time
from datetime import date

db_service = MyDbPostgresService()


# Rate limit query helper
async def count_requests_in_db(column: str, value: str, logger) -> int:
    start_time = time.time()

    query = f"""
        SELECT COUNT(*) FROM openai_requests
        WHERE {column} = %s AND created_at > NOW() - INTERVAL '1 hour'
    """
    result = db_service.fetch_one(query, (value,))

    await asyncio.sleep(0.01)
    end_time = time.time()
    logger.info(f"count_requests_in_db ({column}): {end_time - start_time:.4f} seconds")

    return result[0] if result else 0
