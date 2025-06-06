# import os
#
# import httpx
# from typing import Optional, Dict, Any
# from dotenv import load_dotenv
# # Explicitly load .env file
# env_path = os.path.join(os.path.dirname(__file__), ".env")
# load_dotenv(dotenv_path=env_path)
#
# from backend.app_recipe.config import settings
#
# REVENUECAT_API_KEY = settings.REVENUECAT_API_KEY
# REVENUECAT_BASE_URL = "https://api.revenuecat.com/v1"
#
# print("API KEY:", repr(REVENUECAT_API_KEY))
#
# class RevenueCatError(Exception):
#     pass
#
# def get_revenuecat_headers() -> Dict[str, str]:
#     if not REVENUECAT_API_KEY:
#         raise RevenueCatError("RevenueCat API key is not configured.")
#     # Debug print for API key
#     print("API KEY:", repr(REVENUECAT_API_KEY), "Length:", len(REVENUECAT_API_KEY))
#     return {
#         "Authorization": f"Bearer {REVENUECAT_API_KEY}",
#         "Content-Type": "application/json",
#         "Accept": "application/json"
#     }
#
# async def fetch_revenuecat_api(endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Any:
#     url = f"{REVENUECAT_BASE_URL}{endpoint}"
#     headers = get_revenuecat_headers()
#     async with httpx.AsyncClient() as client:
#         if method.upper() == "GET":
#             response = await client.get(url, headers=headers, params=params)
#         elif method.upper() == "POST":
#             response = await client.post(url, headers=headers, json=data)
#         else:
#             raise RevenueCatError(f"Unsupported HTTP method: {method}")
#         if response.status_code != 200:
#             raise RevenueCatError(f"RevenueCat API error: {response.status_code} - {response.text}")
#         return response.json()
#
# def fetch_revenuecat_api_sync(endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Any:
#     url = f"{REVENUECAT_BASE_URL}{endpoint}"
#     headers = get_revenuecat_headers()
#     with httpx.Client() as client:
#         if method.upper() == "GET":
#             response = client.get(url, headers=headers, params=params)
#         elif method.upper() == "POST":
#             response = client.post(url, headers=headers, json=data)
#         else:
#             raise RevenueCatError(f"Unsupported HTTP method: {method}")
#         if response.status_code != 200:
#             raise RevenueCatError(f"RevenueCat API error: {response.status_code} - {response.text}")
#         return response.json()
#
# async def get_subscriber_info(user_id: str) -> Any:
#     """
#     Fetch subscriber info from RevenueCat for a given user_id.
#     """
#     endpoint = f"/subscribers/{user_id}"
#     return await fetch_revenuecat_api(endpoint, method="GET")
#
# async def get_entitlements() -> Any:
#     """
#     Fetch all entitlements for the project.
#     """
#     endpoint = "/entitlements"
#     return await fetch_revenuecat_api(endpoint, method="GET")
#
# async def get_offerings(app_user_id: Optional[str] = None) -> Any:
#     """
#     Fetch all offerings for the project. Optionally filter by app_user_id.
#     """
#     endpoint = "/offerings"
#     params = {"app_user_id": app_user_id} if app_user_id else None
#     return await fetch_revenuecat_api(endpoint, method="GET", params=params)
#
# async def get_products() -> Any:
#     """
#     Fetch all products for the project.
#     """
#     endpoint = "/products"
#     return await fetch_revenuecat_api(endpoint, method="GET")
#
# async def get_all_receipts(limit: int = 100, next_page: str = None) -> Any:
#     """
#     Fetch all receipts (purchases) from RevenueCat, paginated.
#     """
#     endpoint = "/receipts"
#     params = {"page_size": limit}
#     if next_page:
#         params["next_page"] = next_page
#     return await fetch_revenuecat_api(endpoint, method="GET", params=params)
#
# async def get_purchases_summary() -> dict:
#     """
#     Fetch all receipts and return a summary: total purchases, total revenue, breakdown by product.
#     """
#     all_receipts = []
#     next_page = None
#     while True:
#         data = await get_all_receipts(limit=100, next_page=next_page)
#         receipts = data.get("receipts", [])
#         all_receipts.extend(receipts)
#         next_page = data.get("next_page")
#         if not next_page:
#             break
#
#     summary = {
#         "total_purchases": len(all_receipts),
#         "total_revenue": 0.0,
#         "by_product": {}
#     }
#     for receipt in all_receipts:
#         product_id = receipt.get("product_id")
#         price = float(receipt.get("price", 0))
#         summary["total_revenue"] += price
#         if product_id not in summary["by_product"]:
#             summary["by_product"][product_id] = {"count": 0, "revenue": 0.0}
#         summary["by_product"][product_id]["count"] += 1
#         summary["by_product"][product_id]["revenue"] += price
#
#     return summary
#
# # Example usage (for testing, not for production):
# import asyncio
#
# async def main():
#     try:
#         user_id = "appc3700ef435"
#             print("Fetching subscriber info...")
#         data = await get_subscriber_info(user_id)
#         print("Subscriber info:", data)
#
#         print("\nFetching entitlements...")
#         entitlements = await get_entitlements()
#         print("Entitlements:", entitlements)
#
#         print("\nFetching offerings...")
#         offerings = await get_offerings()
#         print("Offerings:", offerings)
#
#         print("\nFetching products...")
#         products = await get_products()
#         print("Products:", products)
#
#         print("\nFetching purchases summary...")
#         summary = await get_purchases_summary()
#         print("Purchases summary:", summary)
#
#     except Exception as e:
#         print("Error:", e)
#
# if __name__ == "__main__":
#     asyncio.run(main())