from typing import Any, Optional
import time
from functools import wraps
from backend.app.utils.logger import get_logger

logger = get_logger('cache')

class Cache:
    def __init__(self, ttl: int = 300):  # Default TTL: 5 minutes
        self._cache: dict = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and hasn't expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with the current timestamp."""
        self._cache[key] = (value, time.time())
    
    def delete(self, key: str) -> None:
        """Delete a value from the cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all values from the cache."""
        self._cache.clear()

# Create a global cache instance
cache = Cache()

def cached(ttl: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result
            
            # Call the function and cache the result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result)
            logger.debug(f"Cache miss for {cache_key}, result cached")
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str = None):
    """
    Decorator to invalidate cache entries matching a pattern.
    
    Args:
        pattern: Pattern to match against cache keys (if None, clears all cache)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if pattern:
                # Delete cache entries matching the pattern
                keys_to_delete = [k for k in cache._cache.keys() if pattern in k]
                for key in keys_to_delete:
                    cache.delete(key)
                logger.debug(f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}")
            else:
                # Clear all cache
                cache.clear()
                logger.debug("Cleared all cache entries")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator 