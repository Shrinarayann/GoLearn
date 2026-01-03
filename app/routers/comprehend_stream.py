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
    generate_questions,
)
from ..services.fsrs import FSRS
import logging

router = APIRouter()
db = FirestoreService()
fsrs = FSRS()
logger = logging.getLogger(__name__)


class ComprehensionRequest(BaseModel):
    """Request to run comprehension on content."""
    content: Optional[str] = None


async def generate_and_save_quiz(
    session_id: str,
    exploration_result: dict,
    engagement_result: dict,
    application_result: dict
) -> None:
    """
    Generate quiz questions and save to database.
    Called silently after comprehension completes.
    """
    # Get session to check SR setting
    session = await db.get_session(session_id)
    if not session:
        logger.error(f"Session {session_id} not found for quiz generation")
        return
    
    sr_enabled = session.get("enable_spaced_repetition", True)
    
    # Generate questions using agent
    logger.info(f"[Quiz Pre-gen] Generating quiz for session {session_id}")
    questions = await generate_questions(
        exploration=exploration_result,
        engagement=engagement_result,
        application=application_result,
        session_id=session_id
    )
    
    if not questions:
        logger.warning(f"[Quiz Pre-gen] No questions generated for {session_id}")
        return
    
    # Initialize Concepts for FSRS (only if SR enabled)
    now = datetime.utcnow()
    if sr_enabled:
        unique_concepts = list(set([q.get("concept", "general") for q in questions]))
        key_topics = exploration_result.get("key_topics", [])
        for topic in key_topics:
            if topic not in unique_concepts:
                unique_concepts.append(topic)

        for concept_name in unique_concepts:
            existing_concept = await db.get_concept(session_id, concept_name)
            if not existing_concept:
                s, d, _ = fsrs.init_card(3)
                await db.create_concept({
                    "session_id": session_id,
                    "concept_name": concept_name,
                    "stability": s,
                    "difficulty": d,
                    "created_at": now,
                    "next_review_at": now,
                    "times_reviewed": 0,
                    "last_reviewed": None
                })

    # Save questions to Firestore
    for q in questions:
        concept_name = q.get("concept", "general")
        
        if sr_enabled:
            concept_data = await db.get_concept(session_id, concept_name)
            q_data = {
                "session_id": session_id,
                "question": q["question"],
                "correct_answer": q["correct_answer"],
                "question_type": q.get("type", "recall"),
                "difficulty": q.get("difficulty", "medium"),
                "concept": concept_name,
                "explanation": q.get("explanation", ""),
                "leitner_box": 1,
                "created_at": now,
                "next_review_at": now,
                "times_reviewed": 0,
                "stability": concept_data["stability"] if concept_data else 1.0,
                "fsrs_difficulty": concept_data["difficulty"] if concept_data else 5.0
            }
        else:
            q_data = {
                "session_id": session_id,
                "question": q["question"],
                "correct_answer": q["correct_answer"],
                "question_type": q.get("type", "recall"),
                "difficulty": q.get("difficulty", "medium"),
                "concept": concept_name,
                "explanation": q.get("explanation", ""),
                "leitner_box": 1,
                "created_at": now,
                "next_review_at": None,
                "times_reviewed": 0,
                "stability": None,
                "fsrs_difficulty": None
            }
        
        await db.create_question(q_data)
    
    # Update session status to quizzing
    await db.update_session(session_id, {"status": "quizzing"})
    logger.info(f"[Quiz Pre-gen] Saved {len(questions)} questions for session {session_id}")


async def comprehension_event_generator(
    session_id: str,
    content: str,
    pdf_bytes: Optional[bytes],
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events as each comprehension phase completes.
    All 3 phases run in PARALLEL for faster results.
    """
    try:
        # Prepare content (extract text/images from PDF)
        prepared = await prepare_content_for_analysis(content, pdf_bytes, session_id)
        extracted_text = prepared["extracted_text"]
        extracted_images = prepared["extracted_images"]
        content_parts = prepared["content_parts"]
        
        # Update session status to comprehending
        await db.update_session(session_id, {"status": "comprehending"})
        
        # Create a queue to receive results as they complete
        result_queue: asyncio.Queue = asyncio.Queue()
        
        async def run_and_queue_exploration():
            """Run exploration phase and put result in queue."""
            try:
                result = await run_exploration_phase(
                    content_parts=content_parts,
                    session_id=session_id
                )
                await result_queue.put(("exploration", result, None))
            except Exception as e:
                await result_queue.put(("exploration", None, str(e)))
        
        async def run_and_queue_engagement():
            """Run engagement phase and put result in queue."""
            try:
                # Run independently - no previous phase context
                result = await run_engagement_phase(
                    content_parts=content_parts,
                    exploration_result={},  # No context in parallel mode
                    extracted_images=extracted_images,
                    session_id=session_id
                )
                await result_queue.put(("engagement", result, None))
            except Exception as e:
                await result_queue.put(("engagement", None, str(e)))
        
        async def run_and_queue_application():
            """Run application phase and put result in queue."""
            try:
                # Run independently - no previous phase context
                result = await run_application_phase(
                    exploration_result={},  # No context in parallel mode
                    engagement_result={},   # No context in parallel mode
                    session_id=session_id,
                    content_parts=content_parts  # Pass content directly
                )
                await result_queue.put(("application", result, None))
            except Exception as e:
                await result_queue.put(("application", None, str(e)))
        
        # Start all 3 phases in parallel
        tasks = [
            asyncio.create_task(run_and_queue_exploration()),
            asyncio.create_task(run_and_queue_engagement()),
            asyncio.create_task(run_and_queue_application()),
        ]
        
        # Collect results as they complete
        completed = 0
        errors = []
        results = {}  # Store results for quiz generation
        
        while completed < 3:
            phase, result, error = await result_queue.get()
            completed += 1
            
            if error:
                errors.append(f"{phase}: {error}")
                yield f"data: {json.dumps({'phase': 'status', 'message': f'{phase.capitalize()} phase failed: {error}'})}\n\n"
                continue
            
            # Store result for later quiz generation
            results[phase] = result
            
            # Save result to database
            if phase == "exploration":
                await db.update_session(session_id, {"exploration_result": result})
            elif phase == "engagement":
                await db.update_session(session_id, {"engagement_result": result})
            elif phase == "application":
                await db.update_session(session_id, {"application_result": result})
            
            # Yield result to client
            yield f"data: {json.dumps({'phase': phase, 'data': result})}\n\n"
        
        # Wait for all tasks to complete (cleanup)
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update status to ready if no fatal errors
        if len(errors) < 3:  # At least one phase succeeded
            await db.update_session(session_id, {"status": "ready"})
            yield f"data: {json.dumps({'phase': 'complete', 'status': 'ready'})}\n\n"
            
            # Pre-generate quiz in background (silently, no SSE event)
            # This ensures quiz is ready when user clicks "Start Quiz"
            try:
                await generate_and_save_quiz(
                    session_id=session_id,
                    exploration_result=results.get("exploration", {}),
                    engagement_result=results.get("engagement", {}),
                    application_result=results.get("application", {})
                )
            except Exception as quiz_error:
                # Log error but don't fail the comprehension
                import logging
                logging.error(f"Quiz pre-generation failed for {session_id}: {quiz_error}")
        else:
            await db.update_session(session_id, {"status": "error"})
            yield f"data: {json.dumps({'phase': 'error', 'message': 'All phases failed'})}\n\n"
        
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
