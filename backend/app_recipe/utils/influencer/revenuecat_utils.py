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

from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client
from backend.app_recipe.config import settings

# RevenueCat API configuration
# Use the 'Secret API keys' from the RevenueCat dashboard for server-side operations
REVENUECAT_API_KEY = settings.REVENUECAT_API_KEY  # e.g., sk_XOqgwFYOTEFKgDDsGRRgBuakOkBxt

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('revenuecat_routes')


def check_revenuecat_configured():
    """Check if RevenueCat is properly configured"""
    if not REVENUECAT_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="RevenueCat is not configured. Please set REVENUECAT_API_KEY in your environment."
        )


async def verify_revenuecat_webhook(request: Request) -> Dict[str, Any]:
    """Verify RevenueCat webhook signature"""
    try:
        # Check if RevenueCat is configured
        check_revenuecat_configured()

        signature = request.headers.get('X-RevenueCat-Signature')
        # if not signature:
        #     raise HTTPException(status_code=401, detail="Missing RevenueCat signature")

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
