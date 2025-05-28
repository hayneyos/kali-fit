import os
import redis
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get Redis config from env
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

try:
    # Connect to Redis
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True  # Return strings instead of bytes
    )

    # Test connection
    response = r.ping()
    if response:
        print("✅ Redis connection successful!")
        r.set("health_check", "OK")
        print("📦 Redis test key:", r.get("health_check"))
    else:
        print("❌ Redis PING failed")

except redis.AuthenticationError:
    print("❌ Authentication failed: wrong password?")
except Exception as e:
    print("❌ Redis connection failed:", e)
