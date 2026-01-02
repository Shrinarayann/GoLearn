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
            # Enable input transcription to get user's speech as text
            input_audio_transcription=types.AudioTranscriptionConfig(),
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
            
            # Shared flag to signal shutdown
            shutdown_event = asyncio.Event()
            
            # Task to receive from Live API and send to client
            async def receive_from_live_api():
                """
                Receive from Live API continuously.
                The receive() generator ends after each model turn, so we wrap
                in a while loop to keep receiving for multiple turns.
                """
                try:
                    logger.info(f"Starting receive loop for {session_id}")
                    
                    # Keep receiving in a loop - generator ends after each turn
                    while not shutdown_event.is_set():
                        try:
                            async for response in live_session.receive():
                                if shutdown_event.is_set():
                                    logger.info(f"Shutdown signaled, exiting receive for {session_id}")
                                    return
                                    
                                if response.data:
                                    # Audio data from the model
                                    audio_b64 = base64.b64encode(response.data).decode("utf-8")
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": audio_b64
                                    })
                                
                                if response.text:
                                    # Text transcript from the model (agent response)
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "text": response.text
                                    })
                                
                                # Check for user's input transcription
                                if response.server_content:
                                    if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                                        # Extract text from Transcription object
                                        transcription = response.server_content.input_transcription
                                        transcript_text = getattr(transcription, 'text', None) or str(transcription)
                                        if transcript_text:
                                            await websocket.send_json({
                                                "type": "user_transcript",
                                                "text": transcript_text
                                            })
                                    
                                    if response.server_content.turn_complete:
                                        await websocket.send_json({"type": "turn_complete"})
                                        logger.debug(f"Turn complete for {session_id}")
                            
                            # Generator ended for this turn - loop back to wait for next turn
                            logger.debug(f"Receive generator ended for {session_id}, waiting for next turn...")
                            
                        except StopAsyncIteration:
                            # Normal end of turn, continue the loop
                            logger.debug(f"StopAsyncIteration for {session_id}, continuing...")
                            continue
                    
                    logger.info(f"Receive loop exited normally for {session_id}")
                                
                except asyncio.CancelledError:
                    logger.info(f"Live API receive task cancelled for {session_id}")
                    raise
                except Exception as e:
                    logger.error(f"Live API receive error for {session_id}: {e}")
                    shutdown_event.set()
                    if not shutdown_event.is_set():
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Voice processing error: {str(e)}"
                            })
                        except:
                            pass
            
            # Task to receive from client and send to Live API
            async def receive_from_client():
                """Receive messages from WebSocket client until disconnect."""
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
                            # Voice Activity Detection (VAD) handles end-of-speech automatically
                            # Just log this event - no need to send anything to Live API
                            logger.debug(f"User indicated end_turn for {session_id} (VAD handles this)")
                        
                        elif msg_type == "history":
                            # Received conversation history - inject as context
                            history_messages = message.get("messages", [])
                            if history_messages:
                                # Format history as a context message
                                history_text = "Previous conversation for context:\n"
                                for msg in history_messages:
                                    role = "Teacher" if msg.get("role") == "user" else "Student"
                                    history_text += f"{role}: {msg.get('text', '')}\n"
                                history_text += "\nContinue the conversation from where we left off."
                                
                                # Send as text input to provide context
                                await live_session.send(input=history_text)
                                logger.info(f"Injected {len(history_messages)} history messages as context")
                        
                        elif msg_type == "text":
                            # Text input (fallback)
                            await live_session.send(
                                input=message.get("text", "")
                            )
                            
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected from voice session {session_id}")
                except Exception as e:
                    logger.error(f"Client receive error for {session_id}: {e}")
                finally:
                    # Signal shutdown to the receive task
                    shutdown_event.set()
            
            # Run both tasks concurrently
            receive_task = asyncio.create_task(receive_from_live_api())
            send_task = asyncio.create_task(receive_from_client())
            
            try:
                # Wait for the CLIENT task to complete (disconnect)
                # The receive task should keep running until shutdown
                await send_task
                
                # Client disconnected, cancel receive task
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
                        
            except Exception as e:
                logger.error(f"Voice session error for {session_id}: {e}")
                shutdown_event.set()
                receive_task.cancel()
                send_task.cancel()
                
    except Exception as e:
        logger.error(f"Failed to initialize Live API: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to start voice chat: {str(e)}"
            })
            await websocket.close(code=5000)
        except:
            pass
        return
    
    logger.info(f"Voice session ended for {session_id}")
