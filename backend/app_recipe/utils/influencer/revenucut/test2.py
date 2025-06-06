import httpx
import os

# Option 1: Store your secret key securely as an environment variable
# os.environ["REVENUECAT_API_KEY"] = "sk_..."  # set this securely in your environment

REVENUECAT_API_KEY = os.getenv("REVENUECAT_API_KEY", "sk_XOqgwFYOtEFKgDdSgRRgBuakoKBxt")  # fallback to hardcoded (not safe)

def get_subscriber(subscriber_id: str):
    url = f"https://api.revenuecat.com/v1/subscribers/{subscriber_id}"
    headers = {
        "Authorization": f"Bearer {REVENUECAT_API_KEY}",
        "Accept": "application/json"
    }

    try:
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Other error occurred: {e}")
    return None

# 🔧 Replace 'test_user' with your actual subscriber ID
data = get_subscriber("9PTFteyXssflgxVJD3lOpiCsKGh2")
print(data)