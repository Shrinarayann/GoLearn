"""
Authentication routes.
Handles Google Sign-In via Firebase.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from ..dependencies import get_current_user
from ..services.auth_service import verify_google_token, create_or_get_user

router = APIRouter()


class GoogleAuthRequest(BaseModel):
    """Request body for Google Sign-In."""
    id_token: str


class AuthResponse(BaseModel):
    """Authentication response."""
    user_id: str
    email: str
    display_name: str | None
    access_token: str


class UserResponse(BaseModel):
    """Current user response."""
    user_id: str
    email: str
    display_name: str | None


@router.post("/google", response_model=AuthResponse)
async def google_signin(request: GoogleAuthRequest):
    """
    Authenticate with Google Sign-In.
    
    Takes a Google ID token from the frontend and:
    1. Verifies it with Firebase
    2. Creates or retrieves the user in Firestore
    3. Returns user info and a session token
    """
    try:
        # Verify the Google ID token
        decoded = await verify_google_token(request.id_token)
        if not decoded:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token"
            )
        
        # Create or get user in Firestore
        user = await create_or_get_user(
            user_id=decoded["uid"],
            email=decoded.get("email", ""),
            display_name=decoded.get("name", "")
        )
        
        return AuthResponse(
            user_id=user["user_id"],
            email=user["email"],
            display_name=user.get("display_name"),
            access_token=request.id_token  # Frontend will use this for subsequent requests
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user."""
    return UserResponse(
        user_id=current_user["user_id"],
        email=current_user["email"],
        display_name=current_user.get("display_name")
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout the current user.
    Note: Firebase tokens are stateless, so this is mainly for frontend cleanup.
    """
    return {"message": "Logged out successfully"}
