"""
Feynman Technique routes.
Handles interactive teaching sessions with the AI student.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.agent_service import run_feynman_chat, generate_feynman_greeting

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class FeynmanChatMessageRequest(BaseModel):
    """Request to send a message to the Feynman student."""
    message: str


class FeynmanChatMessageResponse(BaseModel):
    """Response from the Feynman student."""
    response: str


# --- Routes ---

@router.post("/sessions/{session_id}/chat", response_model=FeynmanChatMessageResponse)
async def feynman_chat(
    session_id: str,
    request: FeynmanChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Interact with the Feynman student agent.
    The agent acts as a novice learning from the user.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Check if session is ready (must have engagement results for context)
    engagement_result = session.get("engagement_result")
    if not engagement_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must be processed with Three-Pass analysis before starting Feynman Technique."
        )
    
    # Build full context
    study_context = {
        "exploration": session.get("exploration_result", {}),
        "engagement": engagement_result
    }
    
    try:
        # Run interaction
        agent_response = await run_feynman_chat(
            user_message=request.message,
            session_id=session_id,
            study_context=study_context
        )
        
        return FeynmanChatMessageResponse(response=agent_response)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feynman chat failed: {str(e)}"
        )
@router.get("/sessions/{session_id}/greeting", response_model=FeynmanChatMessageResponse)
async def get_feynman_greeting(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get an initial contextual greeting from the Feynman student.
    """
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    engagement_result = session.get("engagement_result")
    if not engagement_result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session not ready."
        )
    
    # Build full context
    study_context = {
        "exploration": session.get("exploration_result", {}),
        "engagement": engagement_result
    }
    
    try:
        greeting = await generate_feynman_greeting(
            session_id=session_id,
            study_context=study_context
        )
        return FeynmanChatMessageResponse(response=greeting)
    except Exception as e:
        return FeynmanChatMessageResponse(response="Hi! I'm ready to learn. What are we studying today?")
