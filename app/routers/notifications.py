"""
Notifications router.
Handles FCM token registration and notification triggers.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any

from ..dependencies import get_current_user
from ..services.notification_service import notification_service

router = APIRouter()

class TokenRegistration(BaseModel):
    """FCM token registration request."""
    token: str

class NotificationTriggerResponse(BaseModel):
    """Response for notification trigger."""
    status: str
    summary: Dict[str, Any]

@router.post("/fcm-token", status_code=status.HTTP_200_OK)
async def register_token(
    request: TokenRegistration,
    current_user: dict = Depends(get_current_user)
):
    """
    Register or update the current user's FCM token.
    """
    success = await notification_service.register_fcm_token(
        user_id=current_user["user_id"],
        token=request.token
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register FCM token"
        )
        
    return {"message": "FCM token registered successfully"}

@router.post("/trigger-check", response_model=NotificationTriggerResponse)
async def trigger_notification_check(
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger a check for due cards and send notifications.
    In a production app, this would be called by a cron job or cloud function.
    """
    # For now, we'll allow any authenticated user to trigger this for testing.
    # In production, this should be restricted to admin or internal callers.
    summary = await notification_service.notify_users_about_due_cards()
    
    return {
        "status": "completed",
        "summary": summary
    }
