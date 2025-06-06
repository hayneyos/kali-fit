import logging
import os
import json
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Body
from fastapi.encoders import jsonable_encoder

from backend.app_recipe.utils.influencer.influencer_mock_data import gen_create_mock
from backend.app_recipe.utils.influencer.influencer_utils import create_influencer, get_influencer_stats, \
    create_referral, get_referrals
from backend.app_recipe.utils.logger import get_logger, LoggerConfig
import os
import json
import logging
from typing import Optional, Dict, Any, List
import time

import firebase_admin
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client
from backend.app_recipe.config import settings
from pydantic import BaseModel


# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('influencer_routes')

router = APIRouter( tags=["influencer"])

@router.get("/promocodes")
async def get_all_promocodes(request: Request):
    code = request.query_params.get("code")
    print(f"Received promocode query param: {code}")
    subscriptions = gen_create_mock()
    body = await request.body()
    response = {
        "transaction": subscriptions,  # כולל breakdown בפנים
        "transaction_breakdown": [row for sub in subscriptions for row in sub["breakdown"]]
    }
    # print(response)
    # print(json.dumps(response, indent=2))
    return response

@router.get("/withdrawals")
async def get_mock_withdrawal_history(request: Request):
    statuses = ["Paid", "Pending", "Failed", "Refunded"]
    now = datetime.utcnow()

    mock_data = []

    for i in range(12):  # simulate 12 months of history
        payout_date = now - timedelta(days=30 * i)
        transaction_date = payout_date - timedelta(days=random.randint(1, 5))
        shares = round(random.uniform(0.5, 3.0), 2)

        mock_data.append({
            "date": payout_date.strftime("%Y-%m"),
            "shares": shares,
            "status": "Paid",
            "request date": payout_date.isoformat(),
            "transaction date": transaction_date.isoformat()
        })

    return {
        "withdrawal_history": mock_data
    }


class InfluencerCreateRequest(BaseModel):
    name: str
    email: str
    social_media_handles: dict
    commission_rate: float = 0.1


@router.post("/influencers")
async def create_influencer_route(request: InfluencerCreateRequest):
    try:
        influencer = create_influencer(
            request.name,
            request.email,
            request.social_media_handles,
            request.commission_rate
        )
        # Convert datetimes to strings
        return JSONResponse(content=jsonable_encoder(influencer))
    except Exception as e:
        logger.error(f"Error creating influencer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/influencers/{influencer_id}/stats")
async def get_influencer_stats_route(
        influencer_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
):
    try:
        stats = get_influencer_stats(influencer_id, start_date, end_date)
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error getting influencer stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ReferralCreateRequest(BaseModel):
    influencer_id: str
    user_id: str
    purchase_amount: float
    purchase_id: str
    original_purchase_id : str


@router.post("/referrals")
async def create_referral_route(request: ReferralCreateRequest):
    try:
        referral = create_referral(
            request.influencer_id,
            request.user_id,
            request.purchase_amount,
            request.purchase_id,
            request.original_purchase_id
        )
        referral["_id"] = str(referral["_id"])
        referral["influencer_id"] = str(referral["influencer_id"])
        return JSONResponse(content=jsonable_encoder(referral))
    except Exception as e:
        logger.error(f"Error creating referral: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/referrals")
async def get_referrals_route(
        influencer_id: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 10
):
    try:
        result = get_referrals(
            influencer_id=influencer_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )
        return JSONResponse(content=jsonable_encoder(result))
    except Exception as e:
        logger.error(f"Error getting referrals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def fix_objectids_and_datetimes(obj):
    if isinstance(obj, list):
        return [fix_objectids_and_datetimes(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: fix_objectids_and_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


@router.get("/influencers/all")
async def get_all_influencers():
    try:
        client = get_mongo_client(db_name="influencer_app")
        influencers_collection = client["revenuecat"]["influencers"]
        influencers = list(influencers_collection.find())
        influencers = fix_objectids_and_datetimes(influencers)
        return JSONResponse(content=influencers)
    except Exception as e:
        logger.error(f"Error getting all influencers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/influencers/by-email/{email}")
async def update_influencer_by_email(email: str, data: dict = Body(...)):
    try:
        client = get_mongo_client(db_name="influencer_app")
        influencers_collection = client["revenuecat"]["influencers"]
        update_data = {k: v for k, v in data.items() if v is not None}
        result = influencers_collection.update_one(
            {"email": email},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Influencer not found")
        updated = influencers_collection.find_one({"email": email})
        # Use the custom encoder
        return JSONResponse(content=fix_objectids_and_datetimes(updated))
    except Exception as e:
        logger.error(f"Error updating influencer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    
@router.get("/influencers/by-email/{email}")
async def get_influencer_by_email(email: str):
    try:
        client = get_mongo_client(db_name="influencer_app")
        influencers_collection = client["revenuecat"]["influencers"]
        influencer = influencers_collection.find_one({"email": email})
        if not influencer:
            raise HTTPException(status_code=404, detail="Influencer not found")
        return JSONResponse(content=fix_objectids_and_datetimes(influencer))
    except Exception as e:
        logger.error(f"Error fetching influencer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class InfluencerAuthRequest(BaseModel):
    email: str
    password: str

@router.post("/authenticate")
async def authenticate_influencer(request: InfluencerAuthRequest):
    try:
        client = get_mongo_client(db_name="influencer_app")
        influencers_collection = client["revenuecat"]["influencers"]
        influencer = influencers_collection.find_one({"email": request.email})
        # if influencer and influencer.get("password") == request.password:
        #todo: should check password
        # if influencer | request.email=='influencer@example.com' | request.email=='admin@lovable.app' :
        if influencer :
            return {"success": True}
        else:
            return {"success": False, "error": "Invalid email or password"}
    except Exception as e:
        logger.error(f"Error authenticating influencer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

