import os
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client
from backend.app_recipe.config import settings

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('revenuecat_routes')

router = APIRouter()

# RevenueCat API configuration
# Use the 'Secret API keys' from the RevenueCat dashboard for server-side operations
REVENUECAT_API_KEY = settings.REVENUECAT_API_KEY  # e.g., sk_XOqgwFYOTEFKgDDsGRRgBuakOkBxt
REVENUECAT_BASE_URL = "https://api.revenuecat.com/v1"

def check_revenuecat_configured():
    """Check if RevenueCat is properly configured"""
    if not REVENUECAT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="RevenueCat is not configured. Please set REVENUECAT_API_KEY in your environment."
        )

# MongoDB collections
def get_influencer_collection():
    client = get_mongo_client()
    return client["recipe_db_v4"]["influencers"]

def get_referral_collection():
    client = get_mongo_client()
    return client["recipe_db_v4"]["referrals"]

async def verify_revenuecat_webhook(request: Request) -> Dict[str, Any]:
    """Verify RevenueCat webhook signature"""
    try:
        # Check if RevenueCat is configured
        check_revenuecat_configured()
        
        signature = request.headers.get('X-RevenueCat-Signature')
        if not signature:
            raise HTTPException(status_code=401, detail="Missing RevenueCat signature")
        
        # Get the raw body
        body = await request.body()
        
        # Verify signature if webhook secret is configured
        if settings.REVENUECAT_WEBHOOK_SECRET:
            # TODO: Implement signature verification
            # This would typically involve verifying the HMAC signature
            # using your RevenueCat webhook secret
            pass
        
        return json.loads(body)
    except Exception as e:
        logger.error(f"Error verifying RevenueCat webhook: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

@router.post("/webhook")
async def revenuecat_webhook(request: Request):
    """Handle RevenueCat webhook events"""
    try:
        # Check if RevenueCat is configured
        check_revenuecat_configured()
        
        # Verify webhook signature
        payload = await verify_revenuecat_webhook(request)
        
        # Log the webhook event
        logger.info(f"Received RevenueCat webhook: {json.dumps(payload)}")
        
        # Handle different event types
        event_type = payload.get('type')
        if event_type == 'INITIAL_PURCHASE':
            # Handle initial purchase
            await handle_initial_purchase(payload)
        elif event_type == 'RENEWAL':
            # Handle renewal
            await handle_renewal(payload)
        elif event_type == 'CANCELLATION':
            # Handle cancellation
            await handle_cancellation(payload)
        elif event_type == 'BILLING_ISSUE':
            # Handle billing issue
            await handle_billing_issue(payload)
        
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"Error processing RevenueCat webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscribers/{user_id}")
async def get_subscriber(user_id: str):
    """Get subscriber information from RevenueCat"""
    try:
        # Check if RevenueCat is configured
        check_revenuecat_configured()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{REVENUECAT_BASE_URL}/subscribers/{user_id}",
                headers={
                    "Authorization": f"Bearer {REVENUECAT_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RevenueCat API error: {response.text}"
                )
            
            return JSONResponse(content=response.json())
    except Exception as e:
        logger.error(f"Error fetching subscriber info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/subscribers/{user_id}/entitlements")
async def grant_entitlement(user_id: str, entitlement_id: str):
    """Grant an entitlement to a subscriber"""
    try:
        # Check if RevenueCat is configured
        check_revenuecat_configured()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{REVENUECAT_BASE_URL}/subscribers/{user_id}/entitlements/{entitlement_id}",
                headers={
                    "Authorization": f"Bearer {REVENUECAT_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "expires_date": None  # Set to None for lifetime access
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"RevenueCat API error: {response.text}"
                )
            
            return JSONResponse(content=response.json())
    except Exception as e:
        logger.error(f"Error granting entitlement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/influencers")
async def create_influencer(
    name: str,
    email: str,
    social_media_handles: Dict[str, str],
    commission_rate: float = 0.1  # Default 10% commission
):
    """Create a new influencer profile"""
    try:
        influencer_collection = get_influencer_collection()
        
        # Check if influencer already exists
        existing = influencer_collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Influencer with this email already exists")
        
        # Generate unique referral code
        referral_code = f"INF{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        influencer = {
            "name": name,
            "email": email,
            "social_media_handles": social_media_handles,
            "referral_code": referral_code,
            "commission_rate": commission_rate,
            "total_referrals": 0,
            "total_earnings": 0.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = influencer_collection.insert_one(influencer)
        influencer["_id"] = str(result.inserted_id)
        
        return JSONResponse(content=influencer)
    except Exception as e:
        logger.error(f"Error creating influencer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/influencers/{influencer_id}/stats")
async def get_influencer_stats(
    influencer_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Get influencer statistics including referrals and earnings"""
    try:
        influencer_collection = get_influencer_collection()
        referral_collection = get_referral_collection()
        
        # Get influencer
        influencer = influencer_collection.find_one({"_id": ObjectId(influencer_id)})
        if not influencer:
            raise HTTPException(status_code=404, detail="Influencer not found")
        
        # Build date filter
        date_filter = {}
        if start_date or end_date:
            date_filter["created_at"] = {}
            if start_date:
                date_filter["created_at"]["$gte"] = start_date
            if end_date:
                date_filter["created_at"]["$lte"] = end_date
        
        # Get referrals
        referrals = list(referral_collection.find({
            "influencer_id": ObjectId(influencer_id),
            **date_filter
        }))
        
        # Calculate statistics
        total_referrals = len(referrals)
        total_earnings = sum(ref.get("commission_amount", 0) for ref in referrals)
        
        # Get daily stats
        daily_stats = {}
        for ref in referrals:
            date = ref["created_at"].date()
            if date not in daily_stats:
                daily_stats[date] = {
                    "referrals": 0,
                    "earnings": 0
                }
            daily_stats[date]["referrals"] += 1
            daily_stats[date]["earnings"] += ref.get("commission_amount", 0)
        
        return JSONResponse(content={
            "influencer": {
                "name": influencer["name"],
                "email": influencer["email"],
                "referral_code": influencer["referral_code"],
                "commission_rate": influencer["commission_rate"]
            },
            "stats": {
                "total_referrals": total_referrals,
                "total_earnings": total_earnings,
                "daily_stats": [
                    {
                        "date": str(date),
                        "referrals": stats["referrals"],
                        "earnings": stats["earnings"]
                    }
                    for date, stats in sorted(daily_stats.items())
                ]
            }
        })
    except Exception as e:
        logger.error(f"Error getting influencer stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/referrals")
async def create_referral(
    influencer_id: str,
    user_id: str,
    purchase_amount: float,
    purchase_id: str
):
    """Create a new referral record"""
    try:
        influencer_collection = get_influencer_collection()
        referral_collection = get_referral_collection()
        
        # Get influencer
        influencer = influencer_collection.find_one({"_id": ObjectId(influencer_id)})
        if not influencer:
            raise HTTPException(status_code=404, detail="Influencer not found")
        
        # Calculate commission
        commission_amount = purchase_amount * influencer["commission_rate"]
        
        # Create referral record
        referral = {
            "influencer_id": ObjectId(influencer_id),
            "user_id": user_id,
            "purchase_amount": purchase_amount,
            "purchase_id": purchase_id,
            "commission_amount": commission_amount,
            "status": "pending",  # pending, paid, cancelled
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = referral_collection.insert_one(referral)
        referral["_id"] = str(result.inserted_id)
        
        # Update influencer stats
        influencer_collection.update_one(
            {"_id": ObjectId(influencer_id)},
            {
                "$inc": {
                    "total_referrals": 1,
                    "total_earnings": commission_amount
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return JSONResponse(content=referral)
    except Exception as e:
        logger.error(f"Error creating referral: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/referrals")
async def get_referrals(
    influencer_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 10
):
    """Get referral records with optional filtering"""
    try:
        referral_collection = get_referral_collection()
        
        # Build filter
        filter_query = {}
        if influencer_id:
            filter_query["influencer_id"] = ObjectId(influencer_id)
        if status:
            filter_query["status"] = status
        if start_date or end_date:
            filter_query["created_at"] = {}
            if start_date:
                filter_query["created_at"]["$gte"] = start_date
            if end_date:
                filter_query["created_at"]["$lte"] = end_date
        
        # Get referrals
        referrals = list(referral_collection.find(filter_query)
                        .sort("created_at", -1)
                        .skip(skip)
                        .limit(limit))
        
        # Convert ObjectId to string
        for ref in referrals:
            ref["_id"] = str(ref["_id"])
            ref["influencer_id"] = str(ref["influencer_id"])
        
        # Get total count
        total = referral_collection.count_documents(filter_query)
        
        return JSONResponse(content={
            "referrals": referrals,
            "total": total,
            "skip": skip,
            "limit": limit
        })
    except Exception as e:
        logger.error(f"Error getting referrals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_initial_purchase(payload: Dict[str, Any]):
    """Handle initial purchase event"""
    try:
        # Extract relevant information
        user_id = payload.get('user_id')
        product_id = payload.get('product_id')
        purchase_amount = float(payload.get('price', 0))
        referral_code = payload.get('referral_code')
        
        # Log the purchase
        logger.info(f"New purchase: User {user_id} purchased {product_id}")
        
        # Handle referral if present
        if referral_code:
            influencer_collection = get_influencer_collection()
            influencer = influencer_collection.find_one({"referral_code": referral_code})
            
            if influencer:
                # Create referral record
                await create_referral(
                    influencer_id=str(influencer["_id"]),
                    user_id=user_id,
                    purchase_amount=purchase_amount,
                    purchase_id=product_id
                )
        
        # TODO: Implement other business logic here
        
    except Exception as e:
        logger.error(f"Error handling initial purchase: {str(e)}")
        raise

async def handle_renewal(payload: Dict[str, Any]):
    """Handle subscription renewal event"""
    try:
        user_id = payload.get('user_id')
        product_id = payload.get('product_id')
        
        logger.info(f"Subscription renewed: User {user_id} renewed {product_id}")
        
        # TODO: Implement renewal logic
        
    except Exception as e:
        logger.error(f"Error handling renewal: {str(e)}")
        raise

async def handle_cancellation(payload: Dict[str, Any]):
    """Handle subscription cancellation event"""
    try:
        user_id = payload.get('user_id')
        product_id = payload.get('product_id')
        
        logger.info(f"Subscription cancelled: User {user_id} cancelled {product_id}")
        
        # TODO: Implement cancellation logic
        
    except Exception as e:
        logger.error(f"Error handling cancellation: {str(e)}")
        raise

async def handle_billing_issue(payload: Dict[str, Any]):
    """Handle billing issue event"""
    try:
        user_id = payload.get('user_id')
        product_id = payload.get('product_id')
        
        logger.info(f"Billing issue: User {user_id} has issue with {product_id}")
        
        # TODO: Implement billing issue handling
        
    except Exception as e:
        logger.error(f"Error handling billing issue: {str(e)}")
        raise 