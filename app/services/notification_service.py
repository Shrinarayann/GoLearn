"""
Notification service.
Handles FCM token registration and sending push notifications for due cards.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from firebase_admin import messaging
from .firebase import FirestoreService, get_firebase_app

logger = logging.getLogger(__name__)
db = FirestoreService()

class NotificationService:
    """Service for handling user notifications."""
    
    def __init__(self):
        self._app = get_firebase_app()

    async def register_fcm_token(self, user_id: str, token: str) -> bool:
        """
        Register or update a user's FCM token.
        
        Args:
            user_id: The ID of the user.
            token: The FCM token from the device.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            await db.update_user(user_id, {
                "fcm_token": token,
                "token_updated_at": datetime.utcnow()
            })
            logger.info(f"Registered FCM token for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register FCM token for user {user_id}: {str(e)}")
            return False

    async def get_users_with_due_cards(self) -> Dict[str, List[str]]:
        """
        Identifies users who have cards due for review.
        
        Returns:
            A dictionary mapping user_id to a list of question_ids that are due.
        """
        now = datetime.utcnow()
        # Query quiz_questions where next_review_at <= now
        # Note: We need to pull all and filter if firestore query is complex, 
        # but here we can try a simple query first.
        # Actually, let's use the optimized approach of fetching all and filtering in-memory
        # if the number of questions is manageable, or better yet, use a proper indexed query if possible.
        
        questions_ref = db.db.collection("quiz_questions")
        query = questions_ref.where("next_review_at", "<=", now)
        
        docs = query.stream()
        
        due_by_user = {}
        
        # To get user_id, we need to look up the session
        # We'll cache session ownership to avoid redundant lookups
        session_to_user = {}
        
        for doc in docs:
            data = doc.to_dict()
            session_id = data.get("session_id")
            question_id = doc.id
            
            if session_id not in session_to_user:
                session = await db.get_session(session_id)
                if session:
                    session_to_user[session_id] = session.get("user_id")
            
            user_id = session_to_user.get(session_id)
            if user_id:
                if user_id not in due_by_user:
                    due_by_user[user_id] = []
                due_by_user[user_id].append(question_id)
                
        return due_by_user

    async def notify_users_about_due_cards(self) -> Dict[str, Any]:
        """
        Finds all users with due cards and sends them a notification.
        
        Returns:
            Summary of notifications sent.
        """
        due_data = await self.get_users_with_due_cards()
        users_notified = 0
        errors = 0
        
        for user_id, question_ids in due_data.items():
            user = await db.get_user(user_id)
            if not user or not user.get("fcm_token"):
                continue
                
            token = user["fcm_token"]
            count = len(question_ids)
            
            success = await self.send_push_notification(
                token=token,
                title="Cards Ready for Review!",
                body=f"You have {count} cards ready for review. Stay on track with your learning!",
                data={"type": "review_due", "count": str(count)}
            )
            
            if success:
                users_notified += 1
            else:
                errors += 1
                
        return {
            "total_users_with_due_cards": len(due_data),
            "users_notified": users_notified,
            "errors": errors
        }

    async def send_push_notification(self, token: str, title: str, body: str, data: Dict[str, str] = None) -> bool:
        """
        Sends a single push notification via FCM.
        """
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )
            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return True
        except Exception as e:
            logger.error(f"Error sending FCM message: {str(e)}")
            return False

# Singleton instance
notification_service = NotificationService()
