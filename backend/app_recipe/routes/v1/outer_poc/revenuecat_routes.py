import os
import json
import logging
import time

import firebase_admin
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from backend.app_recipe.utils.influencer.influencer_utils import create_referral, get_influencer_collection
from backend.app_recipe.utils.influencer.revenuecat_event_handlers import handle_initial_purchase, handle_renewal, \
    handle_cancellation, handle_billing_issue
from backend.app_recipe.utils.influencer.revenuecat_utils import check_revenuecat_configured, verify_revenuecat_webhook
from backend.app_recipe.utils.logger import LoggerConfig, get_logger
from backend.app_recipe.utils.mongo_handler_utils import get_mongo_client

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('revenuecat_routes')

router = APIRouter()

REVENUECAT_BASE_URL = "https://api.revenuecat.com/v1"


from firebase_admin import credentials, firestore

# Initialize Firestore
cred = credentials.Certificate("/home/github/kali_fit/backend/app_recipe/db/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore DB
db = firestore.client()


@router.get("/revenuecat-webhook")
async def revenuecat_webhook(request: Request):
    return JSONResponse(content={"data": "revenuecat-webhook"})

@router.post("/revenuecat-webhook")
async def revenuecat_webhook(request: Request):
    # Check if RevenueCat is configured
    check_revenuecat_configured()

    # Verify webhook signature
    payload = await verify_revenuecat_webhook(request)
    event = payload.get("event", payload)

    # Log the webhook event
    logger.info(f"Received RevenueCat webhook: {json.dumps(payload)}")

    # Store event in MongoDB
    client = get_mongo_client(db_name="influencer_app")
    db_mongo = client["influencer_app"]
    events_collection = db_mongo["revenuecat_events"]
    events_collection.insert_one(jsonable_encoder(event))

    # Store user_id and referral_code for quick lookup
    user_id = event.get("app_user_id") or event.get("original_app_user_id")
    promo_code = (
        event.get("subscriber_attributes", {})
        .get("promo_code_used", {})
        .get("value")
    )

    if (promo_code == "none"):
        referral_code = (
            event.get("subscriber_attributes", {})
            .get("referral_code_used", {})
            .get("value")
        )
    else:
        referral_code = (
            event.get("subscriber_attributes", {})
            .get("promo_code_used", {})
            .get("value")
        )

    # referral_code = "INF20250603180714"
    user_referral_collection = db_mongo["user_referral_codes"]


    if user_id and referral_code:
        user_referral_collection.insert_one({
            "user_id": user_id,
            "referral_code": referral_code,
            "event_type": event.get("type"),
            "timestamp": event.get("event_timestamp_ms", int(time.time() * 1000))
        })

    # Handle different event types
    event_type = event.get('type')
    if event_type == 'INITIAL_PURCHASE':
        await handle_initial_purchase(event)
    elif event_type == 'RENEWAL':
        await handle_renewal(event)
    elif event_type == 'CANCELLATION':
        await handle_cancellation(event)
    elif event_type == 'BILLING_ISSUE':
        await handle_billing_issue(event)

    # --- Firestore logic (unchanged, for RTDN) ---
    print("app_user_id:", event.get("app_user_id"))
    print("original_app_user_id:", event.get("original_app_user_id"))
    subscriber_id = event.get("original_app_user_id")
    event_type = event.get("type", "UNKNOWN")
    timestamp = event.get("event_timestamp_ms", int(time.time() * 1000))

    if not subscriber_id:
        return {"status": "missing_subscriber_id"}

    influencer_collection = get_influencer_collection()
    influencer = influencer_collection.find_one({"referral_code": referral_code})
    influencer_id = str(influencer["_id"])
    referral = create_referral(
        influencer_id,
        event.get("app_user_id"),
        event.get("price"),
        event.get("transaction_id"),
        event.get("original_transaction_id")
    )


    subscriber_data = {
        "app_user_id": event.get("app_user_id"),
        "original_app_user_id": subscriber_id,
        "aliases": event.get("aliases", []),
        "store": event.get("store"),
        "price_usd": event.get("price"),
        "price_local": event.get("price_in_purchased_currency"),
        "currency": event.get("currency"),
        "country_code": event.get("country_code"),
        "entitlement_ids": event.get("entitlement_ids", []),
        "product_id": event.get("product_id"),
        "offering_id": event.get("presented_offering_id"),
        "referral_code": event.get("subscriber_attributes", {}).get("referral_code_used", {}).get("value", "none"),
        "source": event.get("subscriber_attributes", {}).get("source", {}).get("value", "unknown"),
        "event_type": event_type,
        "event_timestamp_ms": timestamp,
        "purchased_at_ms": event.get("purchased_at_ms"),
        "expiration_at_ms": event.get("expiration_at_ms"),
        "environment": event.get("environment"),
        "is_family_share": event.get("is_family_share"),
        "period_type": event.get("period_type"),
        "renewal_number": event.get("renewal_number"),
    }

    try:
        db.collection("subscribers").document(subscriber_id).set(subscriber_data, merge=True)
        db.collection("subscribers").document(subscriber_id) \
            .collection("events").add({
            "event_type": event_type,
            "timestamp": timestamp,
            **event
        })
    except Exception as exp:
        print(exp)

    response = {"status": "ok", "subscriber_data": subscriber_data}
    logger.info(response)
    return response
