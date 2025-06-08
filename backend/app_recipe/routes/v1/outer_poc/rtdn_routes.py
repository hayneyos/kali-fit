import os

from fastapi import APIRouter, Request, Header
import base64
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from backend.app_recipe.utils.logger import LoggerConfig, get_logger

# Configure logger
logger_config = LoggerConfig(
    log_dir=os.getenv('LOG_DIR', 'logs'),
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('revenuecat_routes')

# Initialize Firebase only if not already initialized
try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate("/home/github/kaila-train/backend/app/db/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Initialize Google Play Developer API
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]
GOOGLE_SERVICE_ACCOUNT = "/home/github/kaila-train/subscription/loyal-world-400303-fde67ddeb9f8.json"
google_credentials = service_account.Credentials.from_service_account_file(
    GOOGLE_SERVICE_ACCOUNT, scopes=GOOGLE_SCOPES
)
android_publisher = build("androidpublisher", "v3", credentials=google_credentials)

# Map subscription types
SUBSCRIPTION_TYPE_MAP = {
    1: "SUBSCRIPTION_RECOVERED",
    2: "SUBSCRIPTION_RENEWED",
    3: "SUBSCRIPTION_CANCELED",
    4: "SUBSCRIPTION_PURCHASED",
    5: "SUBSCRIPTION_ON_HOLD",
    6: "SUBSCRIPTION_IN_GRACE_PERIOD",
    7: "SUBSCRIPTION_RESTARTED",
    8: "SUBSCRIPTION_PRICE_CHANGE_CONFIRMED",
    12: "SUBSCRIPTION_DEFERRED",
    13: "SUBSCRIPTION_PAUSED",
    14: "SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED",
    15: "SUBSCRIPTION_REVOKED",
    16: "SUBSCRIPTION_EXPIRED"
}

router = APIRouter()


def get_subscription_info(package_name: str, subscription_id: str, purchase_token: str):
    try:
        result = android_publisher.purchases().subscriptions().get(
            packageName=package_name,
            subscriptionId=subscription_id,
            token=purchase_token
        ).execute()
        return result
    except Exception as e:
        print(f"❌ Error retrieving subscription: {e}")
        return None


@router.post("/rtdn")
async def handle_rtdn(
        request: Request,
        ce_type: str = Header(None),
        ce_specversion: str = Header(None),
        ce_source: str = Header(None),
        ce_id: str = Header(None),
        ce_time: str = Header(None)
):
    envelope = await request.json()
    logger.info("Raw Envelope:", envelope)

    if "message" not in envelope:
        return {"error": "Missing 'message' field"}

    message = envelope["message"]
    data_b64 = message.get("data")
    if not data_b64:
        return {"error": "Missing 'data'"}
    result = {}
    try:
        # Decode and parse message
        decoded = base64.b64decode(data_b64).decode("utf-8")
        data = json.loads(decoded)
        logger.info("Decoded RTDN:", data)

        # Structure document to store
        doc = {
            "raw": data,
            "receivedAt": firestore.SERVER_TIMESTAMP,
            "eventType": None,
            "packageName": data.get("packageName"),
        }

        if "subscriptionNotification" in data:
            sub = data["subscriptionNotification"]
            doc["eventType"] = SUBSCRIPTION_TYPE_MAP.get(sub.get("notificationType"), "UNKNOWN")
            doc["purchaseToken"] = sub.get("purchaseToken")
            doc["subscriptionId"] = sub.get("subscriptionId")

            # Try to get full purchase information from Google API
            purchase_info = get_subscription_info(
                data.get("packageName"),
                sub.get("subscriptionId"),
                sub.get("purchaseToken")
            )

            if purchase_info:
                doc["purchaseInfo"] = purchase_info
                logger.info(f"purchaseInfo {purchase_info}")
                result = {
                    "eventType": doc["eventType"],
                    "packageName": data.get("packageName"),
                    "subscriptionId": sub.get("subscriptionId"),
                    "orderId": purchase_info.get("orderId"),
                    "price": int(purchase_info.get("priceAmountMicros", 0)) / 1_000_000,
                    "currency": purchase_info.get("priceCurrencyCode"),
                    "startTime": purchase_info.get("startTimeMillis"),
                    "expiryTime": purchase_info.get("expiryTimeMillis"),
                    "autoRenewing": purchase_info.get("autoRenewing"),
                }
        elif "oneTimeProductNotification" in data:
            otp = data["oneTimeProductNotification"]
            doc["eventType"] = f"ONE_TIME_{otp.get('notificationType')}"
            doc["purchaseToken"] = otp.get("purchaseToken")
            doc["sku"] = otp.get("sku")

        elif "testNotification" in data:
            doc["eventType"] = "TEST_NOTIFICATION"

        else:
            doc["eventType"] = "UNKNOWN"

        # Save to Firestore
        db.collection("rtdn_event").add(doc)
        logger.info(f"✅ RTDN saved to Firestore: {doc["eventType"]}", )

        # Print useful information

    except Exception as e:
        logger.error("❌ Error:", str(e))
        return {"error": "Invalid message"}

    response = {"status": "ok", "result": result}
    logger.info(response)
    return response
