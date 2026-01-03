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
from ..services.storage_service import upload_file_to_storage, delete_session_files
from ..services.agent_service import run_comprehension
from ..services.pdf_image_service import extract_images_from_pdf_bytes_as_base64

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class CreateSessionRequest(BaseModel):
    """Request to create a new study session."""
    title: str
    content: Optional[str] = None  # Optional text content
    enable_spaced_repetition: bool = True  # Enable quiz/spaced repetition (default: True)


class SessionResponse(BaseModel):
    """Study session response."""
    session_id: str
    user_id: str
    title: str
    status: str
    created_at: datetime
    enable_spaced_repetition: bool = True
    pdf_filename: Optional[str] = None
    exploration_result: Optional[dict] = None
    engagement_result: Optional[dict] = None
    application_result: Optional[dict] = None


class SessionListItem(BaseModel):
    """Lightweight session item for list view (no comprehension data)."""
    session_id: str
    title: str
    status: str
    created_at: datetime
    enable_spaced_repetition: bool = True


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
    extracted_images: Optional[List[dict]] = None  # Images from PDF for display


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
        "enable_spaced_repetition": request.enable_spaced_repetition,
    }
    
    session_id = await db.create_session(session_data)
    
    return SessionResponse(
        session_id=session_id,
        user_id=current_user["user_id"],
        title=request.title,
        status="created",
        created_at=session_data["created_at"],
        enable_spaced_repetition=request.enable_spaced_repetition,
    )


@router.get("/sessions", response_model=List[SessionListItem])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """List all study sessions for the current user (lightweight, no comprehension data)."""
    sessions = await db.get_user_sessions_summary(current_user["user_id"])
    return [
        SessionListItem(
            session_id=s["session_id"],
            title=s["title"],
            status=s["status"],
            created_at=s["created_at"],
            enable_spaced_repetition=s.get("enable_spaced_repetition", True),
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
        session_id=session["session_id"],
        user_id=session["user_id"],
        title=session["title"],
        status=session["status"],
        created_at=session["created_at"],
        enable_spaced_repetition=session.get("enable_spaced_repetition", True),  # Default True for existing sessions
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
    current_user: dict = Depends(get_current_user),
    request: ComprehensionRequest = None,
    file: Optional[UploadFile] = File(None)
):
    """
    Run the three-pass comprehension on the study material.
    This executes exploration, engagement, and application agents.
    
    Can accept either:
    - Text content in request body
    - PDF file upload (processed directly, not stored)
    - Both text and PDF
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get content and PDF bytes
    content = (request and request.content) or session.get("raw_content", "")
    pdf_bytes = None
    
    # If PDF file uploaded, read bytes directly
    if file and file.filename.lower().endswith(".pdf"):
        pdf_bytes = await file.read()
    
    # Check if we have any content to analyze
    if not content and not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content to analyze. Provide text or upload a PDF."
        )
    
    # Update status
    await db.update_session(session_id, {"status": "comprehending"})
    
    try:
        # Run comprehension agents (PDF bytes processed directly, not stored)
        results = await run_comprehension(
            content=content,
            session_id=session_id,
            pdf_bytes=pdf_bytes
        )
        
        # Save results to session (use _for_storage fields to avoid nested entity issues)
        await db.update_session(session_id, {
            "status": "ready",
            "exploration_result": results.get("exploration_for_storage", results["exploration"]),
            "engagement_result": results.get("engagement_for_storage", results["engagement"]),
            "application_result": results.get("application_for_storage", results["application"]),
        })
        
        return ComprehensionResponse(
            session_id=session_id,
            status="ready",
            exploration=results["exploration"],
            engagement=results["engagement"],
            application=results["application"],
            extracted_images=results.get("extracted_images", []),
        )
        
    except Exception as e:
        await db.update_session(session_id, {"status": "error"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comprehension failed: {str(e)}"
        )


@router.post("/sessions/{session_id}/extract-images")
async def extract_pdf_images(
    session_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    min_width: int = 100,
    min_height: int = 100,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 85
):
    """
    Extract images from an uploaded PDF and return them as base64-encoded data URLs.
    Images are automatically resized to medium size for efficiency.
    Does NOT save images to disk or storage.
    
    Parameters:
    - file: PDF file to extract images from
    - min_width/min_height: Minimum dimensions to filter tiny icons (default 100px)
    - max_width/max_height: Maximum dimensions for optimization (default 800px)
    - quality: JPEG compression quality 1-100 (default 85)
    
    Returns:
    - JSON with total count and array of base64-encoded images with metadata
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
    
    try:
        # Read PDF file bytes
        pdf_bytes = await file.read()
        
        # Extract images as base64
        result = extract_images_from_pdf_bytes_as_base64(
            pdf_bytes=pdf_bytes,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height,
            quality=quality,
            deduplicate=True
        )
        
        return {
            "session_id": session_id,
            "filename": file.filename,
            "total_images": result["total_images"],
            "images": result["images"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image extraction failed: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Permanently delete a study session and all associated data.
    """
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    try:
        # 1. Delete associated data in Firestore
        await db.delete_session_questions(session_id)
        await db.delete_session_concepts(session_id)
        
        # 2. Delete files in Storage
        await delete_session_files(session_id)
        
        # 3. Delete the session itself
        await db.delete_session(session_id)
        
        return {"message": "Session and all associated data deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )

