"""
Chat router with RAG-powered responses.
"""

import json
import logging
from typing import Optional, List, AsyncGenerator
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import google.generativeai as genai

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.rag_service import retrieve_relevant_chunks
from ..config import settings

router = APIRouter()
db = FirestoreService()
logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GOOGLE_API_KEY)


class ChatRequest(BaseModel):
    message: str


async def chat_response_generator(
    session_id: str,
    user_message: str,
    relevant_chunks: list,
    chat_history: list
) -> AsyncGenerator[str, None]:
    context_parts = []
    if relevant_chunks:
        context_parts.append("=== RELEVANT STUDY MATERIAL ===")
        for i, chunk in enumerate(relevant_chunks, 1):
            context_parts.append(f"[Section {i}]: {chunk.get('text', '')}")
        context_parts.append("=== END ===")
    context = "\n".join(context_parts)
    
    history_parts = []
    for msg in chat_history[-5:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_parts.append(f"{role}: {msg.get('content', '')}")
    history_text = "\n".join(history_parts)
    
    prompt = f"""You are a helpful study assistant. Answer based ONLY on the study material.
If the answer is not in the material, say "I don't have that in your notes."

{context}

{"Chat history:\n" + history_text + "\n" if history_text else ""}User: {user_message}"""
    
    # Use Gemini to generate streaming response
    try:
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(prompt, stream=True)
        
        full_response = ""
        for chunk in response:
            if chunk.text:
                full_response += chunk.text
                # Yield SSE formatted data
                yield f"data: {json.dumps({'content': chunk.text})}\n\n"
        
        # Save assistant message to history
        await db.add_chat_message(session_id, {
            "role": "assistant",
            "content": full_response
        })
        
        # Send completion signal
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    except Exception as e:
        logger.error(f"Chat generation error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: str,
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a chat message and get streaming response."""
    # Verify session ownership
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Save user message
    await db.add_chat_message(session_id, {
        "role": "user",
        "content": request.message
    })
    
    # Get chat history
    chat_history = await db.get_chat_history(session_id, limit=10)
    
    # Get relevant chunks via RAG
    try:
        relevant_chunks = await retrieve_relevant_chunks(
            session_id=session_id,
            query=request.message,
            db=db,
            top_k=5
        )
    except Exception as e:
        logger.warning(f"RAG retrieval failed, using empty context: {e}")
        relevant_chunks = []
    
    # Return streaming response
    return StreamingResponse(
        chat_response_generator(
            session_id=session_id,
            user_message=request.message,
            relevant_chunks=relevant_chunks,
            chat_history=chat_history
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/sessions/{session_id}/history")
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get chat history for a session."""
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    history = await db.get_chat_history(session_id, limit=50)
    return {"messages": history}
