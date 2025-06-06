import requests

api_key = "sk_XOqgwFYOTEFKgDDsGRRgBuakOkBxt"
print(f"Using API key: {api_key}")

user_ids = [
    "aPmOjbGoFMOvIQQVWthg0AGLkn2",
    "9PTFteyXssflgxVJDlOpiCsKGh2",
    "$RCAnonymousID:8b83bd208438489f80ba930061d7dce5",
]

headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "application/json"
}

for user_id in user_ids:
    url = f"https://api.revenuecat.com/v1/subscribers/{user_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Extract summary info
        entitlements = data["subscriber"].get("entitlements", {})
        first_entitlement = next(iter(entitlements.values()), {})
        print({
            "user_id": user_id,
            "active": first_entitlement.get("expires_date") is not None,
            "is_trial": first_entitlement.get("is_trial_period"),
            "product": first_entitlement.get("product_identifier"),
        })
    else:
        print(f"Error for {user_id}: {response.status_code}")