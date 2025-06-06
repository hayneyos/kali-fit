import random
import uuid
from datetime import datetime, timedelta

import pandas as pd
from dateutil.relativedelta import relativedelta

subscription_types = ["monthly", "yearly", "Discounted Yearly"]
platforms = ["android", "ios"]
referral_names = ["Alice", "Bob", "Charlie", "Dana", "Eli", "Fatima", "George", "Hila", "Ivan", "Judy"]


def random_date(start_days_ago=90):
    start = datetime.now() - timedelta(days=random.randint(0, start_days_ago))
    end = start + timedelta(days=365)
    return start, end


def generate_device(platform):
    if platform == "android":
        return {
            "model": "sdk_gphone64_arm64",
            "manufacturer": "Google",
            "androidVersion": "14",
            "device": "emu64a"
        }
    else:
        return {
            "model": "iPhone13,2",
            "iosVersion": "18.4.1",
            "name": "iPhone"
        }


def generate_transaction_breakdown(subscriptions, existing_ids=None):
    """
    Generate 12-month transaction breakdowns for yearly subscriptions.
    `existing_ids` should be a set of IDs that already exist in the transaction_break_down table.
    """
    breakdown = []
    if existing_ids is None:
        existing_ids = set()

    for sub in subscriptions:
        sub_type = sub.get("subscriptionType")
        sub_id = sub.get("id")

        if sub_id in existing_ids:
            continue  # skip if already processed

        if sub_type not in ["yearly", "Discounted Yearly"]:
            continue

        try:
            start = datetime.fromisoformat(sub["startDate"])
        except:
            continue

        monthly_price = round(sub["price"] / 12, 2)

        for i in range(12):
            month_date = start + relativedelta(months=i)
            breakdown.append({
                "parent_id": sub_id,
                "userId": sub["userId"],
                "month": month_date.strftime("%Y-%m"),
                "price": monthly_price,
                "referralName": sub.get("referralName", ""),
                "code": sub.get("code", ""),
                "platform": sub.get("platform", ""),
                "subscriptionType": sub_type,
                "device": sub.get("device", {}),
                "timestamp": datetime.now().isoformat(),
            })

    return breakdown


def gen_create_mock():
    subscriptions = []
    statuses = ['Active', 'Paid', 'Cancelled', 'Refunded']

    for _ in range(1000):
        subscription_type = random.choice(subscription_types)
        platform = random.choice(platforms)
        start_date, end_date = random_date()
        user_id = str(uuid.uuid4())
        code = f"DEV{random.randint(100, 999)}"
        referral_name = random.choice(referral_names)
        total_price = 3 if subscription_type == "monthly" else (36 if subscription_type == "yearly" else 28.8)
        sub_id = f"{code}_{user_id}"
        device = generate_device(platform)

        # Randomly decide if the whole subscription is refunded
        is_refunded = random.random() < 0.1  # 10% chance

        breakdown = []
        factor = 1

        if subscription_type == "monthly":
            payout_date = start_date + timedelta(days=2)
            status = "Refunded" if is_refunded else random.choices(statuses[:-1], weights=[0.8, 0.1, 0.1])[0]
            if (status == 'Refunded'):
                factor = -1

            breakdown.append({
                "month": start_date.strftime("%Y-%m"),
                "payoutDate": payout_date.isoformat(),
                "price": factor * total_price * 0.2,
                "status": "Refunded" if is_refunded else status
            })

        else:
            # monthly_price = round(total_price / 12, 2)
            monthly_price = round(total_price, 2)
            for i in range(1):
                month_date = start_date + pd.DateOffset(months=i)
                payout_date = (month_date + timedelta(days=1)) if i != 0 else (start_date + timedelta(days=2))
                status = "Refunded" if is_refunded else (
                    "Future" if i != 0 else random.choices(statuses[:-1], weights=[0.85, 0.1, 0.05])[0]
                )

                if (status == 'Refunded'):
                    factor = -1

                breakdown.append({
                    "month": month_date.strftime("%Y-%m"),
                    "payoutDate": payout_date.isoformat(),
                    "price": factor * monthly_price * 0.2,
                    "status": status
                })

        subscriptions.append({
            "id": sub_id,
            "subscriptionType": subscription_type,
            "platform": platform,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "timestamp": datetime.now().isoformat(),
            "lastValidated": datetime.now().isoformat(),
            "userId": user_id,
            "price": total_price,
            "productId": "promo_code",
            "code": code,
            "device": device,
            "referralName": referral_name,
            "breakdown": breakdown,
            "status": "Refunded" if is_refunded else "Active"
        })

    return subscriptions
