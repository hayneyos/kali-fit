import requests
import json
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

BASE_URL = "http://localhost:8091"  # Change if your server runs elsewhere

def test_create_influencer():
    url = f"{BASE_URL}/influencers"
    data = {
        "name": "Test Influencer",
        "email": " admin@lovable.app",
        "social_media_handles": {"instagram": "@test", "tiktok": "@testtok"},
        "commission_rate": 0.15
    }
    response = requests.post(url, json=data)
    print("Create Influencer:", response.status_code, response.json())
    return response.json().get("_id") or response.json().get("id")


def test_get_influencer_stats(influencer_id):
    url = f"{BASE_URL}/influencers/{influencer_id}/stats"
    response = requests.get(url)
    print("Get Influencer Stats:", response.status_code, response.json())


def test_create_referral(influencer_id):
    url = f"{BASE_URL}/referrals"
    data = {
        "influencer_id": influencer_id,
        "user_id": "user123",
        "purchase_amount": 49.99,
        "purchase_id": "purchase_abc"
    }
    response = requests.post(url, json=data)
    print("Create Referral:", response.status_code, response.json())


def test_get_referrals(influencer_id):
    url = f"{BASE_URL}/referrals"
    params = {"influencer_id": influencer_id}
    response = requests.get(url, params=params)
    print("Get Referrals:", response.status_code, response.json())


class ReferralCreateRequest(BaseModel):
    influencer_id: str
    user_id: str
    purchase_amount: float
    purchase_id: str


if __name__ == "__main__":
    # 1. Create influencer
    influencer_id = test_create_influencer()
    if not influencer_id:
        print("Failed to create influencer, aborting tests.")
        exit(1)

    # 2. Get influencer stats
    test_get_influencer_stats(influencer_id)

    # 3. Create a referral
    test_create_referral(influencer_id)

    # 4. Get referrals
    test_get_referrals(influencer_id)
