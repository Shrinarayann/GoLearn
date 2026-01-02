"""
Exam generation routes.
Handles exam paper generation from study sessions.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.exam_generator_service import generate_exam

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class ExamStatusResponse(BaseModel):
    """Exam generation status response."""
    status: str  # idle, generating, ready, error
    pdf_url: Optional[str] = None
    error: Optional[str] = None
    generated_at: Optional[datetime] = None


class ExamGenerateResponse(BaseModel):
    """Response when starting exam generation."""
    message: str
    status: str


# --- Routes ---

@router.post("/generate/{session_id}", response_model=ExamGenerateResponse)
async def start_exam_generation(
    session_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Start exam generation for a study session.
    
    This endpoint:
    1. Validates the session and file
    2. Starts background generation task
    3. Returns immediately so user can continue browsing
    
    Use GET /exam/sessions/{session_id}/status to poll for completion.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    # Check if session has completed comprehension
    if session.get("status") not in ["ready", "quizzing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must complete comprehension before generating exam"
        )
    
    # Check if already generating
    exam_status = await db.get_exam_status(session_id)
    if exam_status["status"] == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam generation already in progress"
        )
    
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported as sample papers"
        )
    
    # Read file bytes
    sample_paper_bytes = await file.read()
    
    # Start background task
    background_tasks.add_task(
        generate_exam,
        session_id=session_id,
        sample_paper_bytes=sample_paper_bytes,
        user_id=current_user["user_id"]
    )
    
    # Mark as generating immediately
    await db.update_exam_status(session_id, "generating")
    
    return ExamGenerateResponse(
        message="Exam generation started. Poll /exam/sessions/{session_id}/status for updates.",
        status="generating"
    )


@router.get("/sessions/{session_id}/status", response_model=ExamStatusResponse)
async def get_exam_status(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the current exam generation status for a session.
    
    Returns:
        - status: 'idle' | 'generating' | 'ready' | 'error'
        - pdf_url: Download URL when status is 'ready'
        - error: Error message when status is 'error'
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    exam_status = await db.get_exam_status(session_id)
    
    return ExamStatusResponse(
        status=exam_status["status"],
        pdf_url=exam_status.get("pdf_url"),
        error=exam_status.get("error"),
        generated_at=exam_status.get("generated_at")
    )


@router.delete("/sessions/{session_id}/reset")
async def reset_exam_status(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Reset exam status to idle, allowing regeneration.
    Useful after errors or if user wants to regenerate with different sample.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session"
        )
    
    await db.update_exam_status(session_id, "idle")
    
    return {"message": "Exam status reset to idle"}
