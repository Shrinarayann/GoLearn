"""
Chat routes.
Handles AI chat with Gemini using study session context.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
import google.generativeai as genai

from ..config import settings
from ..dependencies import get_current_user

router = APIRouter()

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)


# --- Schemas ---

class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request for chat completion."""
    message: str
    history: List[ChatMessage] = []
    context: Optional[str] = None  # Study content context


class ChatResponse(BaseModel):
    """Chat response."""
    response: str


# --- Routes ---

@router.post("/chat", response_model=ChatResponse)
async def chat_with_gemini(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat with Gemini using study session context.
    The context from exploration, engagement, and application phases
    is provided to help answer questions about the study material.
    """
    try:
        # Build the system prompt with context
        system_prompt = """You are a helpful study assistant for GoLearn, an educational platform. 
Your role is to help students understand their study material better by answering their questions clearly and concisely.

Guidelines:
- Keep responses brief and focused (2-3 paragraphs max)
- Use simple language to explain complex concepts
- Reference the study material context when relevant
- If asked about something not in the context, politely mention that and provide general guidance
- Be encouraging and supportive"""

        if request.context:
            system_prompt += f"""

Here is the study material context the student is learning:
---
{request.context}
---

Use this context to answer questions about the material. If the question is unrelated to the context, you can still help but mention that it's outside the current study material."""

        # Initialize model - Using Gemini 2.0 Flash
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=system_prompt
        )

        # Build chat history for context
        chat_history = []
        for msg in request.history:
            chat_history.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.content]
            })

        # Start chat with history
        chat = model.start_chat(history=chat_history)

        # Send the message and get response
        response = chat.send_message(request.message)

        return ChatResponse(response=response.text)

    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get response from AI: {str(e)}"
        )
