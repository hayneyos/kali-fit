from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from bson import ObjectId
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client
from backend.app_recipe.utils.logger import get_logger

logger = get_logger('influencer_utils')

def get_influencer_collection():
    client = get_mongo_client(db_name="influencer_app")
    return client["revenuecat"]["influencers"]

def get_referral_collection():
    client = get_mongo_client(db_name="influencer_app")
    return client["revenuecat"]["referrals"]

def create_influencer(name: str, email: str, social_media_handles: Dict[str, str], commission_rate: float = 0.1, password: str = "password123") -> Dict[str, Any]:
    influencer_collection = get_influencer_collection()
    existing = influencer_collection.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Influencer with this email already exists")
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
        "updated_at": datetime.utcnow(),
        # WARNING: Storing plain text passwords is insecure. Use hashing in production!
        "password": password
    }
    result = influencer_collection.insert_one(influencer)
    influencer["_id"] = str(result.inserted_id)
    return influencer

def get_influencer_stats(influencer_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, Any]:
    influencer_collection = get_influencer_collection()
    referral_collection = get_referral_collection()
    influencer = influencer_collection.find_one({"_id": ObjectId(influencer_id)})
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")
    date_filter = {}
    if start_date or end_date:
        date_filter["created_at"] = {}
        if start_date:
            date_filter["created_at"]["$gte"] = start_date
        if end_date:
            date_filter["created_at"]["$lte"] = end_date
    referrals = list(referral_collection.find({
        "influencer_id": ObjectId(influencer_id),
        **date_filter
    }))
    total_referrals = len(referrals)
    total_earnings = sum(ref.get("commission_amount", 0) for ref in referrals)
    daily_stats = {}
    for ref in referrals:
        date = ref["created_at"].date()
        if date not in daily_stats:
            daily_stats[date] = {"referrals": 0, "earnings": 0}
        daily_stats[date]["referrals"] += 1
        daily_stats[date]["earnings"] += ref.get("commission_amount", 0)
    return {
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
    }

def create_referral(influencer_id: str, user_id: str, purchase_amount: float, purchase_id: str, original_purchase_id: str) -> Dict[str, Any]:
    influencer_collection = get_influencer_collection()
    referral_collection = get_referral_collection()
    influencer = influencer_collection.find_one({"_id": ObjectId(influencer_id)})
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")
    commission_amount = purchase_amount * (influencer["commission_rate"] / 100.0)
    referral = {
        "influencer_id": ObjectId(influencer_id),
        "user_id": user_id,
        "purchase_amount": purchase_amount,
        "purchase_id": purchase_id,
        "original_purchase_id": original_purchase_id,
        "commission_amount": commission_amount,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = referral_collection.insert_one(referral)
    referral["_id"] = str(result.inserted_id)
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
    return referral

def get_referrals(
    influencer_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 10
) -> Dict[str, Any]:
    referral_collection = get_referral_collection()
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
    referrals = list(referral_collection.find(filter_query)
                     .sort("created_at", -1)
                     .skip(skip)
                     .limit(limit))
    for ref in referrals:
        ref["_id"] = str(ref["_id"])
        ref["influencer_id"] = str(ref["influencer_id"])
    total = referral_collection.count_documents(filter_query)
    return {
        "referrals": referrals,
        "total": total,
        "skip": skip,
        "limit": limit
    } 