"""
Study session routes.
Handles study session creation, PDF upload, and comprehension.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from pydantic import BaseModel
from datetime import datetime

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.storage_service import upload_file_to_storage
from ..services.agent_service import run_comprehension

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class CreateSessionRequest(BaseModel):
    """Request to create a new study session."""
    title: str
    content: Optional[str] = None  # Optional text content


class SessionResponse(BaseModel):
    """Study session response."""
    session_id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    pdf_filename: Optional[str] = None
    exploration_result: Optional[dict] = None
    engagement_result: Optional[dict] = None
    application_result: Optional[dict] = None


class ComprehensionRequest(BaseModel):
    """Request to run comprehension on content."""
    content: Optional[str] = None  # If not provided, will use stored content


class ComprehensionResponse(BaseModel):
    """Comprehension results."""
    session_id: str
    status: str
    exploration: dict
    engagement: dict
    application: dict


# --- Routes ---

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new study session."""
    session_data = {
        "user_id": current_user["user_id"],
        "title": request.title,
        "status": "created",
        "created_at": datetime.utcnow(),
        "raw_content": request.content or "",
    }
    
    session_id = await db.create_session(session_data)
    
    return SessionResponse(
        session_id=session_id,
        user_id=current_user["user_id"],
        title=request.title,
        status="created",
        created_at=session_data["created_at"],
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """List all study sessions for the current user."""
    sessions = await db.get_user_sessions(current_user["user_id"])
    return [
        SessionResponse(
            session_id=s["session_id"],
            user_id=s["user_id"],
            title=s["title"],
            status=s["status"],
            created_at=s["created_at"],
            pdf_filename=s.get("pdf_filename"),
            exploration_result=s.get("exploration_result"),
            engagement_result=s.get("engagement_result"),
            application_result=s.get("application_result"),
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific study session."""
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
    
    return SessionResponse(
        session_id=session_id,
        user_id=session["user_id"],
        title=session["title"],
        status=session["status"],
        created_at=session["created_at"],
        pdf_filename=session.get("pdf_filename"),
        exploration_result=session.get("exploration_result"),
        engagement_result=session.get("engagement_result"),
        application_result=session.get("application_result"),
    )


@router.post("/sessions/{session_id}/upload")
async def upload_pdf(
    session_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a PDF file to a study session.
    The file is stored in Firebase Storage and its URL saved to the session.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Upload to Firebase Storage
    file_url = await upload_file_to_storage(
        file=file,
        path=f"sessions/{session_id}/{file.filename}"
    )
    
    # Update session with file URL
    await db.update_session(session_id, {
        "pdf_url": file_url,
        "pdf_filename": file.filename,
        "status": "uploaded"
    })
    
    return {
        "message": "File uploaded successfully",
        "file_url": file_url,
        "filename": file.filename
    }


@router.post("/sessions/{session_id}/comprehend", response_model=ComprehensionResponse)
async def run_comprehension_endpoint(
    session_id: str,
    request: ComprehensionRequest = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Run the three-pass comprehension on the study material.
    This executes exploration, engagement, and application agents.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get content to analyze
    content = (request and request.content) or session.get("raw_content", "")
    if not content and not session.get("pdf_url"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content to analyze. Upload a PDF or provide text."
        )
    
    # Update status
    await db.update_session(session_id, {"status": "comprehending"})
    
    try:
        # Run comprehension agents
        results = await run_comprehension(
            content=content,
            session_id=session_id,
            pdf_url=session.get("pdf_url")
        )
        
        # Save results to session
        await db.update_session(session_id, {
            "status": "ready",
            "exploration_result": results["exploration"],
            "engagement_result": results["engagement"],
            "application_result": results["application"],
        })
        
        return ComprehensionResponse(
            session_id=session_id,
            status="ready",
            exploration=results["exploration"],
            engagement=results["engagement"],
            application=results["application"],
        )
        
    except Exception as e:
        await db.update_session(session_id, {"status": "error"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comprehension failed: {str(e)}"
        )
