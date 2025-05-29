# from fastapi import Request, HTTPException
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.responses import Response
# import time
# import redis
# from backend.app_recipe.config import settings
# from backend.app_recipe.utils.logger import get_logger
#
# logger = get_logger(__name__)
#
# class RateLimitMiddleware(BaseHTTPMiddleware):
#     def __init__(self, app, redis_client=None):
#         super().__init__(app)
#         self.redis_client = redis_client or self._create_redis_client()
#         self.rate_limit = 100  # requests per minute
#         self.window = 60  # 1 minute window
#
#     def _create_redis_client(self):
#         """Create a Redis client with the configured settings."""
#         try:
#             return redis.Redis(
#                 host=settings.REDIS_HOST,
#                 port=settings.REDIS_PORT,
#                 password=settings.REDIS_PASSWORD or None,
#                 decode_responses=True
#             )
#         except Exception as e:
#             logger.error(f"Failed to create Redis client: {e}")
#             return None
#
#     async def dispatch(self, request: Request, call_next):
#         if not self.redis_client:
#             logger.warning("Redis client not available, skipping rate limiting")
#             return await call_next(request)
#
#         client_ip = request.client.host
#         current_time = int(time.time())
#         window_key = f"rate_limit:{client_ip}:{current_time // self.window}"
#
#         try:
#             # Increment the counter for this window
#             count = self.redis_client.incr(window_key)
#
#             # Set expiry on the key if this is the first request in the window
#             if count == 1:
#                 self.redis_client.expire(window_key, self.window)
#
#             # Check if rate limit is exceeded
#             if count > self.rate_limit:
#                 logger.warning(f"Rate limit exceeded for IP: {client_ip}")
#                 raise HTTPException(
#                     status_code=429,
#                     detail="Too many requests. Please try again later."
#                 )
#
#             # Process the request
#             response = await call_next(request)
#             return response
#
#         except redis.RedisError as e:
#             logger.error(f"Redis error during rate limiting: {e}")
#             return await call_next(request)
#         except HTTPException:
#             raise
#         except Exception as e:
#             logger.error(f"Unexpected error during rate limiting: {e}")
#             return await call_next(request)