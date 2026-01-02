"""
Voice chat routes using Gemini Multimodal Live API.
Handles real-time audio streaming for Feynman voice interactions.
"""

import asyncio
import base64
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from google import genai
from google.genai import types

from ..services.firebase import FirestoreService

router = APIRouter()
db = FirestoreService()
logger = logging.getLogger(__name__)

# Load Feynman system prompt
_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "study_agent", "prompts", "feynman.txt"
)
with open(_PROMPT_PATH, "r") as f:
    _FEYNMAN_INSTRUCTION = f.read()


def _build_voice_system_prompt(study_context: dict, topic: Optional[str] = None) -> str:
    """Build the system prompt for voice Feynman sessions."""
    # Format study context as a readable summary
    context_str = ""
    if study_context.get("exploration"):
        exp = study_context["exploration"]
        if exp.get("summary"):
            context_str += f"Summary: {exp['summary']}\n"
        if exp.get("key_topics"):
            context_str += f"Key Topics: {', '.join(exp['key_topics'])}\n"
    
    if study_context.get("engagement"):
        eng = study_context["engagement"]
        if eng.get("concept_explanations"):
            concepts = list(eng["concept_explanations"].keys())[:5]
            context_str += f"Key Concepts: {', '.join(concepts)}\n"
    
    if not context_str:
        context_str = "General study material"
    
    # Replace placeholder in instruction
    instruction = _FEYNMAN_INSTRUCTION.replace("{study_context}", context_str)
    
    # Add voice-specific guidance
    voice_guidance = """

## Voice Interaction Guidelines
- Keep responses SHORT and conversational (1-3 sentences max)
- Use natural speech patterns with "um", "hmm", "wait..." for authenticity
- Express confusion verbally: "Wait, I'm lost..." or "Hmm, can you say that again?"
- Sound genuinely curious and a bit overwhelmed, not robotic
- Ask ONE question at a time to keep the conversation flowing
"""
    
    if topic:
        voice_guidance += f"\n- Current topic being taught: {topic}"
    
    return instruction + voice_guidance


async def _verify_token_and_get_user(token: str) -> Optional[dict]:
    """Verify JWT token and return user info."""
    try:
        import firebase_admin.auth as firebase_auth
        decoded = firebase_auth.verify_id_token(token)
        return {"user_id": decoded["uid"], "email": decoded.get("email")}
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


@router.websocket("/feynman/{session_id}/voice")
async def feynman_voice_chat(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint for real-time voice chat with the Feynman agent.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 PCM audio>"}
    - Client sends: {"type": "end_turn"} to signal end of speech
    - Server sends: {"type": "audio", "data": "<base64 PCM audio>"}
    - Server sends: {"type": "turn_complete"} when agent finishes speaking
    - Server sends: {"type": "transcript", "text": "..."} for transcriptions
    - Server sends: {"type": "error", "message": "..."} for errors
    """
    await websocket.accept()
    logger.info(f"Voice WebSocket connection accepted for session {session_id}")
    
    # Verify authentication
    user = await _verify_token_and_get_user(token)
    if not user:
        await websocket.send_json({"type": "error", "message": "Authentication failed"})
        await websocket.close(code=4001)
        return
    
    # Load session data
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["user_id"]:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close(code=4004)
        return
    
    # Build study context
    study_context = {
        "exploration": session.get("exploration_result", {}),
        "engagement": session.get("engagement_result", {})
    }
    
    # Get topic from query or use session title
    topic = session.get("current_topic") or session.get("title")
    
    # Build system prompt
    system_prompt = _build_voice_system_prompt(study_context, topic)
    
    # Initialize Gemini Live API client
    try:
        client = genai.Client(
            http_options={"api_version": "v1alpha"}
        )
        
        # Configure Live API session
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"  # Friendly, curious voice
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=system_prompt)]
            )
        )
        
        # Connect to Live API
        async with client.aio.live.connect(
            model="gemini-2.0-flash-exp",
            config=config
        ) as live_session:
            
            await websocket.send_json({"type": "connected", "message": "Voice chat ready"})
            logger.info(f"Live API session established for {session_id}")
            
            # Task to receive from Live API and send to client
            async def receive_from_live_api():
                try:
                    async for response in live_session.receive():
                        if response.data:
                            # Audio data from the model
                            audio_b64 = base64.b64encode(response.data).decode("utf-8")
                            await websocket.send_json({
                                "type": "audio",
                                "data": audio_b64
                            })
                        
                        if response.text:
                            # Text transcript
                            await websocket.send_json({
                                "type": "transcript",
                                "text": response.text
                            })
                        
                        if response.server_content and response.server_content.turn_complete:
                            await websocket.send_json({"type": "turn_complete"})
                            
                except Exception as e:
                    logger.error(f"Live API receive error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Voice processing error: {str(e)}"
                    })
            
            # Task to receive from client and send to Live API
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive_json()
                        msg_type = message.get("type")
                        
                        if msg_type == "audio":
                            # Decode and send audio to Live API
                            audio_data = base64.b64decode(message["data"])
                            await live_session.send(
                                input=types.LiveClientRealtimeInput(
                                    media_chunks=[
                                        types.Blob(
                                            data=audio_data,
                                            mime_type="audio/pcm;rate=16000"
                                        )
                                    ]
                                )
                            )
                        
                        elif msg_type == "end_turn":
                            # Signal end of user speech
                            await live_session.send(
                                input=types.LiveClientRealtimeInput(
                                    turn_complete=True
                                )
                            )
                        
                        elif msg_type == "text":
                            # Text input (fallback)
                            await live_session.send(
                                input=message.get("text", "")
                            )
                            
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected from voice session {session_id}")
                except Exception as e:
                    logger.error(f"Client receive error: {e}")
            
            # Run both tasks concurrently
            receive_task = asyncio.create_task(receive_from_live_api())
            send_task = asyncio.create_task(receive_from_client())
            
            try:
                # Wait for either task to complete (usually client disconnect)
                done, pending = await asyncio.wait(
                    [receive_task, send_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
            except Exception as e:
                logger.error(f"Voice session error: {e}")
                
    except Exception as e:
        logger.error(f"Failed to initialize Live API: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to start voice chat: {str(e)}"
        })
        await websocket.close(code=5000)
        return
    
    logger.info(f"Voice session ended for {session_id}")
