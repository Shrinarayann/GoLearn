"""
Feynman Technique routes.
Handles interactive teaching sessions with the AI student.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.agent_service import run_feynman_chat, generate_feynman_greeting, evaluate_mastery

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class FeynmanChatMessageRequest(BaseModel):
    """Request to send a message to the Feynman student."""
    message: str


class FeynmanChatMessageResponse(BaseModel):
    """Response from the Feynman student."""
    response: str

class FeynmanTopicMastery(BaseModel):
    """Mastery info for a specific topic."""
    score: int
    updated_at: Optional[datetime] = None

class FeynmanTopic(BaseModel):
    """A specific topic and its current mastery."""
    name: str
    mastery: Optional[FeynmanTopicMastery] = None

class FeynmanTopicsResponse(BaseModel):
    """List of available topics for a session."""
    topics: List[FeynmanTopic]

class FeynmanEvaluateRequest(BaseModel):
    """Request to evaluate mastery of a topic."""
    topic: str
    transcript: List[dict]

class FeynmanEvaluateResponse(BaseModel):
    """Result of a mastery evaluation."""
    score: int
    feedback: str


# --- Routes ---

@router.post("/sessions/{session_id}/chat", response_model=FeynmanChatMessageResponse)
async def feynman_chat(
    session_id: str,
    request: FeynmanChatMessageRequest,
    topic: Optional[str] = None,
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
            study_context=study_context,
            topic=topic
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
    topic: Optional[str] = None,
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
            study_context=study_context,
            topic=topic
        )
        return FeynmanChatMessageResponse(response=greeting)
    except Exception as e:
        return FeynmanChatMessageResponse(response="Hi! I'm ready to learn. What are we studying today?")


@router.get("/sessions/{session_id}/topics", response_model=FeynmanTopicsResponse)
async def get_feynman_topics(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get available topics for a session (from Pass 1 & 2 analysis).
    """
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    
    exploration = session.get("exploration_result", {})
    engagement = session.get("engagement_result", {})
    
    # Extract names from key topics and concept explanations
    topic_set = set()
    if exploration.get("key_topics"):
        topic_set.update(exploration["key_topics"])
    if engagement.get("concept_explanations"):
        topic_set.update(engagement["concept_explanations"].keys())
        
    # Get current mastery from session
    mastery_map = session.get("feynman_mastery", {})
    
    topics = []
    for t_name in sorted(list(topic_set)):
        mastery_info = mastery_map.get(t_name)
        mastery = None
        if mastery_info:
            mastery = FeynmanTopicMastery(
                score=mastery_info.get("score", 0),
                updated_at=mastery_info.get("updated_at")
            )
        topics.append(FeynmanTopic(name=t_name, mastery=mastery))
        
    return FeynmanTopicsResponse(topics=topics)


@router.post("/sessions/{session_id}/evaluate", response_model=FeynmanEvaluateResponse)
async def feynman_evaluate(
    session_id: str,
    request: FeynmanEvaluateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluate mastery based on a chat transcript and update DB.
    """
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    
    study_context = {
        "exploration": session.get("exploration_result", {}),
        "engagement": session.get("engagement_result", {})
    }
    
    try:
        result = await evaluate_mastery(
            transcript=request.transcript,
            topic=request.topic,
            study_context=study_context
        )
        
        # Save to DB
        await db.update_feynman_mastery(
            session_id=session_id,
            topic=request.topic,
            score=result["score"]
        )
        
        return FeynmanEvaluateResponse(
            score=result["score"],
            feedback=result["feedback"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
