#
#
# @router.get("/subscribers/{user_id}")
# async def get_subscriber(user_id: str):
#     """Get subscriber information from RevenueCat"""
#     try:
#         # Check if RevenueCat is configured
#         check_revenuecat_configured()
#
#         async with httpx.AsyncClient() as client:
#             response = await client.get(
#                 f"{REVENUECAT_BASE_URL}/subscribers/{user_id}",
#                 headers={
#                     "Authorization": f"Bearer {REVENUECAT_API_KEY}",
#                     "Content-Type": "application/json"
#                 }
#             )
#
#             if response.status_code != 200:
#                 raise HTTPException(
#                     status_code=response.status_code,
#                     detail=f"RevenueCat API error: {response.text}"
#                 )
#
#             return JSONResponse(content=response.json())
#     except Exception as e:
#         logger.error(f"Error fetching subscriber info: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @router.post("/subscribers/{user_id}/entitlements")
# async def grant_entitlement(user_id: str, entitlement_id: str):
#     """Grant an entitlement to a subscriber"""
#     try:
#         # Check if RevenueCat is configured
#         check_revenuecat_configured()
#
#         async with httpx.AsyncClient() as client:
#             response = await client.post(
#                 f"{REVENUECAT_BASE_URL}/subscribers/{user_id}/entitlements/{entitlement_id}",
#                 headers={
#                     "Authorization": f"Bearer {REVENUECAT_API_KEY}",
#                     "Content-Type": "application/json"
#                 },
#                 json={
#                     "expires_date": None  # Set to None for lifetime access
#                 }
#             )
#
#             if response.status_code != 200:
#                 raise HTTPException(
#                     status_code=response.status_code,
#                     detail=f"RevenueCat API error: {response.text}"
#                 )
#
#             return JSONResponse(content=response.json())
#     except Exception as e:
#         logger.error(f"Error granting entitlement: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))
