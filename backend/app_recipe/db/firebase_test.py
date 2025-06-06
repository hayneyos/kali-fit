
import requests
from firebase_admin import credentials, firestore, initialize_app

# === Firebase Init ===
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred)
db = firestore.client()

# === Default values for missing fields ===
DEFAULTS = {
    "platform": "web",
    "goal": "Maintain Weight"
}

# === Function ===
def update_user_from_survey_api(user_id: str, user_obj: dict):
    # Add fallback defaults if missing
    for field, default_value in DEFAULTS.items():
        if field not in user_obj:
            print(f"ℹ️ Field '{field}' is missing. Using default: {default_value}")
            user_obj[field] = default_value

    # Step 1: Send to external survey API
    # try:
    #     response = requests.post("https://for-checking.online/api/survey", json={"user": user_obj})
    #     response.raise_for_status()
    #     survey_response = response.json()
    #     print("✅ Received survey response")
    # except requests.RequestException as e:
    #     print(f"❌ API request failed: {e}")
    #     return

    # Step 2: Update Firestore
    user_ref = db.collection("users").document(user_id)
    update_data = {
        "survey": survey_response,
        "profile": {
            "displayName": user_obj.get("displayName"),
            "email": user_obj.get("email"),
            "platform": user_obj.get("platform"),
            "goal": user_obj.get("goal")
        },
        "updatedAt": user_obj.get("updatedAt")
    }
    user_ref.set(update_data, merge=True)
    print(f"✅ Firestore user {user_id} updated with survey + profile data.")

# === Example Call ===
sample_user = {
    "birthDate": "2000-10-27T00:00:00.000",
    "calories": 1628,
    "carbs": 203,
    "createdAt": "2025-04-22T06:46:09Z",
    "dietType": "Pescatarian",
    "fats": 36,
    "gender": "Female",
    "hasCompletedWizard": True,
    "height": "145",
    "isAnonymous": True,
    "language": "English",
    "lastLogin": "2025-04-22T06:46:09Z",
    "protein": 122,
    "updatedAt": "2025-04-21T23:46:07.524965",
    "weight": "43",
    "displayName": "Dmytro Polskoi",
    "email": "dmytro.polskoi@icloud.com"
}

update_user_from_survey_api("test!!!!!!!!!", sample_user)
