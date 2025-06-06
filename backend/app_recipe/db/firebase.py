import firebase_admin
import pandas as pd
from firebase_admin import credentials, firestore
from typing import Optional, Dict, Any

cred = credentials.Certificate("/home/github/kali_fit/backend/app_recipe/db/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Initialize Firestore DB
db = firestore.client()


class FirestoreService:
    def __init__(self):
        self.promocodes_ref = db.collection("promocodes")

        self.analyzed_meals_ref = db.collection("analyzed_meals")
        self.deletion_requests_ref = db.collection("deletionRequests")
        self.notifications_ref = db.collection("notifications")
        self.subscriptions_ref = db.collection("subscriptions")
        self.users_ref = db.collection("users")
        self.wizard_ref = db.collection("wizard")  # Add this reference


    # === USERS ===
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        doc = self.users_ref.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def create_or_update_user(self, user_id: str, data: Dict[str, Any]):
        self.users_ref.document(user_id)


    # === ANALYZED MEALS ===
    def get_meals_for_user(self, user_id: str):
        return list(self.analyzed_meals_ref.where("userId", "==", user_id).stream())

    # === DELETION REQUESTS ===
    def create_deletion_request(self, user_id: str):
        self.deletion_requests_ref.document(user_id).set({"requestedAt": firestore.SERVER_TIMESTAMP})

    # === NOTIFICATIONS ===
    def send_notification(self, user_id: str, message: str):
        self.notifications_ref.add({"userId": user_id, "message": message, "sentAt": firestore.SERVER_TIMESTAMP})

    # === SUBSCRIPTIONS ===
    def get_user_subscription(self, user_id: str):
        docs = self.subscriptions_ref.where("userId", "==", user_id).stream()
        return [doc.to_dict() for doc in docs]

        # === SURVEY DATA ===

    def get_user_data(self, user_id):
        doc =self.users_ref.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def save_survey_data(self, user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Save or update survey data and return the stored document."""
        self.users_ref.document(user_id).set(data, merge=True)
        doc = self.users_ref.document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def get_all_users_with_wizard(self) -> list[dict]:
        """Efficiently get all users merged with their wizard data."""

        # Fetch all users
        user_docs = list(self.users_ref.stream())
        users_data = []
        for user_doc in user_docs:
            if user_doc.exists:
                data = user_doc.to_dict()
                data['user_id'] = user_doc.id  # Save the Firestore doc ID
                users_data.append(data)

        if not users_data:
            return []

        users_df = pd.DataFrame(users_data)

        # Fetch all wizards
        wizard_docs = list(self.wizard_ref.stream())
        wizards_data = []
        for wizard_doc in wizard_docs:
            if wizard_doc.exists:
                data = wizard_doc.to_dict()
                data['wizard_id'] = wizard_doc.id  # Save the Firestore doc ID
                wizards_data.append(data)

        if not wizards_data:
            wizards_df = pd.DataFrame(columns=["wizard_id"])
        else:
            wizards_df = pd.DataFrame(wizards_data)

        # Merge users with their corresponding wizards
        merged_df = users_df.merge(
            wizards_df,
            left_on="wizardId",
            right_on="wizard_id",
            how="left",
            suffixes=("_user", "_wizard")
        )

        # Convert back to list of dicts
        merged_records = merged_df.to_dict(orient="records")
        return merged_records

    def get_all_users_with_wizard_slow(self) -> list[dict]:
        """Get all users combined with their wizard data."""
        result = []

        users = self.users_ref.stream()
        for user_doc in users:
            if not user_doc.exists:
                continue

            user_data = user_doc.to_dict()
            user_id = user_doc.id

            wizard_data = {}
            wizard_id = user_data.get("wizardId")

            if wizard_id:
                wizard_doc = self.wizard_ref.document(wizard_id).get()
                if wizard_doc.exists:
                    wizard_data = wizard_doc.to_dict()

            combined_data = {
                "user_id": user_id,
                "user": user_data,
                "wizard": wizard_data
            }
            result.append(combined_data)

        return result

    def get_all_promocodes(self) -> list[dict]:
        """Fetch all documents from the promocodes collection."""
        promo_docs = self.promocodes_ref.stream()
        return [doc.to_dict() | {"id": doc.id} for doc in promo_docs if doc.exists]