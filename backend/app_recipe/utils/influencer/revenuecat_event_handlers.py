import logging
from typing import Dict, Any

from backend.app_recipe.utils.influencer.influencer_utils import get_influencer_collection, create_referral
from backend.app_recipe.utils.logger import get_logger

logger = get_logger('revenuecat_event_handlers')


async def handle_initial_purchase(payload: Dict[str, Any]):
    """Handle initial purchase event"""
    try:
        # Extract relevant information
        user_id = payload.get('app_user_id')
        aliases = payload.get('aliases')
        original_app_user_id = payload.get('original_app_user_id')

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
                    purchase_id=product_id,
                    original_app_user_id=product_id
                )

        # TODO: Implement other business logic here

    except Exception as e:
        logger.error(f"Error handling initial purchase: {str(e)}")
        raise


async def handle_renewal(payload: Dict[str, Any]):
    """Handle subscription renewal event"""
    try:
        app_user_id = payload.get('app_user_id')
        aliases = payload.get('aliases')
        original_app_user_id = payload.get('original_app_user_id')

        product_id = payload.get('product_id')

        logger.info(f"Subscription renewed: app_user_id {app_user_id}  renewed {product_id}")
        logger.info(f"Subscription renewed: original_app_user_id {original_app_user_id}  renewed {product_id}")
        logger.info(f"Subscription renewed: aliases {aliases}  renewed {product_id}")

        # TODO: Implement renewal logic

    except Exception as e:
        logger.error(f"Error handling renewal: {str(e)}")
        raise


async def handle_cancellation(payload: Dict[str, Any]):
    """Handle subscription cancellation event"""
    try:
        app_user_id = payload.get('app_user_id')
        aliases = payload.get('aliases')
        original_app_user_id = payload.get('original_app_user_id')
        product_id = payload.get('product_id')

        logger.info(f"Subscription renewed: app_user_id {app_user_id}  cancelled {product_id}")
        logger.info(f"Subscription renewed: original_app_user_id {original_app_user_id}  cancelled {product_id}")
        logger.info(f"Subscription renewed: aliases {aliases}  cancelled {product_id}")

        # TODO: Implement cancellation logic

    except Exception as e:
        logger.error(f"Error handling cancellation: {str(e)}")
        raise


async def handle_billing_issue(payload: Dict[str, Any]):
    """Handle billing issue event"""
    try:
        app_user_id = payload.get('app_user_id')
        aliases = payload.get('aliases')
        original_app_user_id = payload.get('original_app_user_id')
        product_id = payload.get('product_id')

        event = "Billing issue"
        logger.info(f"{event}: app_user_id {app_user_id}  has issue with {product_id}")
        logger.info(f"{event}: original_app_user_id {original_app_user_id}  has issue with {product_id}")
        logger.info(f"{event}: aliases {aliases}  has issue with {product_id}")

        # TODO: Implement billing issue handling

    except Exception as e:
        logger.error(f"Error handling billing issue: {str(e)}")
        raise
