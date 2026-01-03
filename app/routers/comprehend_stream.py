"""
Streaming comprehension endpoint for three-phase analysis.
Uses Server-Sent Events (SSE) to progressively stream results.
"""

import json
import asyncio
from typing import Optional, List, AsyncGenerator
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.agent_service import (
    run_exploration_phase,
    run_engagement_phase,
    run_application_phase,
    prepare_content_for_analysis,
)

router = APIRouter()
db = FirestoreService()


class ComprehensionRequest(BaseModel):
    """Request to run comprehension on content."""
    content: Optional[str] = None


async def comprehension_event_generator(
    session_id: str,
    content: str,
    pdf_bytes: Optional[bytes],
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events as each comprehension phase completes.
    """
    try:
        # Prepare content (extract text/images from PDF)
        prepared = await prepare_content_for_analysis(content, pdf_bytes, session_id)
        extracted_text = prepared["extracted_text"]
        extracted_images = prepared["extracted_images"]
        content_parts = prepared["content_parts"]
        
        # Update session status to comprehending
        await db.update_session(session_id, {"status": "comprehending"})
        
        # Phase 1: Exploration
        yield f"data: {json.dumps({'phase': 'status', 'message': 'Starting exploration phase...'})}\n\n"
        
        exploration_result = await run_exploration_phase(
            content_parts=content_parts,
            session_id=session_id
        )
        
        # Save exploration result immediately
        await db.update_session(session_id, {
            "exploration_result": exploration_result
        })
        
        yield f"data: {json.dumps({'phase': 'exploration', 'data': exploration_result})}\n\n"
        
        # Phase 2: Engagement
        yield f"data: {json.dumps({'phase': 'status', 'message': 'Starting engagement phase...'})}\n\n"
        
        engagement_result = await run_engagement_phase(
            content_parts=content_parts,
            exploration_result=exploration_result,
            extracted_images=extracted_images,
            session_id=session_id
        )
        
        # Save engagement result immediately
        await db.update_session(session_id, {
            "engagement_result": engagement_result
        })
        
        yield f"data: {json.dumps({'phase': 'engagement', 'data': engagement_result})}\n\n"
        
        # Phase 3: Application
        yield f"data: {json.dumps({'phase': 'status', 'message': 'Starting application phase...'})}\n\n"
        
        application_result = await run_application_phase(
            exploration_result=exploration_result,
            engagement_result=engagement_result,
            session_id=session_id
        )
        
        # Save application result and update status to ready
        await db.update_session(session_id, {
            "application_result": application_result,
            "status": "ready"
        })
        
        yield f"data: {json.dumps({'phase': 'application', 'data': application_result})}\n\n"
        
        # Final completion event
        yield f"data: {json.dumps({'phase': 'complete', 'status': 'ready'})}\n\n"
        
    except Exception as e:
        # Send error event
        await db.update_session(session_id, {"status": "error"})
        yield f"data: {json.dumps({'phase': 'error', 'message': str(e)})}\n\n"


@router.post("/sessions/{session_id}/comprehend-stream")
async def comprehend_stream(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    request: ComprehensionRequest = None,
    file: Optional[UploadFile] = File(None)
):
    """
    Run the three-pass comprehension with SSE streaming.
    
    Returns a stream of JSON events as each phase completes:
    - { phase: "status", message: "..." } - Status updates
    - { phase: "exploration", data: {...} } - Exploration results
    - { phase: "engagement", data: {...} } - Engagement results
    - { phase: "application", data: {...} } - Application results
    - { phase: "complete", status: "ready" } - Completion signal
    - { phase: "error", message: "..." } - Error if any
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
    
    return StreamingResponse(
        comprehension_event_generator(
            session_id=session_id,
            content=content,
            pdf_bytes=pdf_bytes,
            user_id=current_user["user_id"]
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
