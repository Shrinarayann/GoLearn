"""
Authentication service.
Handles Firebase Auth token verification.
"""

from typing import Optional
from firebase_admin import auth

from .firebase import get_firebase_app, FirestoreService

db = FirestoreService()


async def verify_google_token(id_token: str) -> Optional[dict]:
    """
    Verify a Google ID token using Firebase Auth.
    
    Args:
        id_token: The ID token from Google Sign-In
        
    Returns:
        Decoded token claims if valid, None otherwise
    """
    get_firebase_app()
    
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded
    except auth.InvalidIdTokenError:
        return None
    except auth.ExpiredIdTokenError:
        return None
    except Exception:
        return None


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token for API authentication.
    
    Args:
        token: The Firebase ID token from Authorization header
        
    Returns:
        User dict if valid, None otherwise
    """
    get_firebase_app()
    
    try:
        decoded = auth.verify_id_token(token)
        
        # Get or create user in Firestore
        user = await db.get_user(decoded["uid"])
        if not user:
            user = await create_or_get_user(
                user_id=decoded["uid"],
                email=decoded.get("email", ""),
                display_name=decoded.get("name", "")
            )
        
        return user
        
    except Exception:
        return None


async def create_or_get_user(
    user_id: str, 
    email: str, 
    display_name: str = ""
) -> dict:
    """
    Create a new user or get existing one.
    
    Args:
        user_id: Firebase UID
        email: User's email
        display_name: User's display name
        
    Returns:
        User dict
    """
    # Check if user exists
    existing = await db.get_user(user_id)
    if existing:
        return existing
    
    # Create new user
    user_data = {
        "user_id": user_id,
        "email": email,
        "display_name": display_name,
    }
    await db.create_user(user_data)
    
    return user_data
