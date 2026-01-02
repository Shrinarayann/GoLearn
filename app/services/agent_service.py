"""
Agent service.
Runs ADK agents from FastAPI endpoints using the ADK Runner.
"""

from typing import Optional
import google.generativeai as genai
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import httpx
import tempfile
import os
import asyncio
import logging
import json
from datetime import datetime

from ..config import settings

# Import ADK comprehension orchestrator
from study_agent.comprehension.orchestrator import comprehension_orchestrator
from study_agent.feynman import feynman_agent

# Setup logging
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'agent_outputs.log')),
        logging.StreamHandler()
    ]
)

# Configure Gemini API
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Create a singleton session service for ADK
_session_service = InMemorySessionService()

# Create the ADK Runner for comprehension
_comprehension_runner = Runner(
    agent=comprehension_orchestrator,
    app_name="golearn",
    session_service=_session_service
)

# Create the ADK Runner for Feynman
_feynman_runner = Runner(
    agent=feynman_agent,
    app_name="golearn",
    session_service=_session_service
)


async def run_comprehension(
    content: str,
    session_id: str,
    pdf_url: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None
) -> dict:
    """
    Run the three-pass comprehension using ADK agents.
    
    Uses the ADK Runner to properly execute the comprehension_orchestrator,
    which runs exploration_agent -> engagement_agent -> application_agent in sequence.
    
    Args:
        content: Text content to analyze
        session_id: Session ID for tracking
        pdf_url: Optional URL to PDF file
        pdf_bytes: Optional raw PDF bytes
        
    Returns:
        dict with exploration, engagement, and application results
    """
    uploaded_file = None
    
    # If we have a PDF URL, download it
    if pdf_url and not pdf_bytes:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(pdf_url)
                if response.status_code == 200:
                    pdf_bytes = response.content
        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
    
    # Build message content parts
    content_parts = []
    
    # If we have PDF bytes, upload to Gemini and create a Part
    if pdf_bytes:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
            # Create a Part from the uploaded file URI
            content_parts.append(types.Part(
                file_data=types.FileData(
                    file_uri=uploaded_file.uri,
                    mime_type="application/pdf"
                )
            ))
            logger.info(f"Uploaded PDF to Gemini: {uploaded_file.name}")
        finally:
            os.unlink(tmp_path)
    
    # Add text content if provided
    if content:
        content_parts.append(types.Part(text=content))
    
    # If no content at all, error
    if not content_parts:
        raise ValueError("No content provided for analysis")
    
    logger.info(f"\n{'='*80}\nSTARTING ADK THREE-PASS ANALYSIS (Session: {session_id})\n{'='*80}")
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"Content length: {len(content) if content else 0} chars")
    logger.info(f"Has PDF: {pdf_bytes is not None}")
    
    # Create the message content
    message = types.Content(
        role="user",
        parts=content_parts
    )
    
    # Create a fresh ADK session for this comprehension run
    # This is needed because InMemorySessionService doesn't auto-create sessions
    await _session_service.create_session(
        app_name="golearn",
        user_id="golearn",
        session_id=session_id,
        state={},  # Empty initial state
    )
    logger.info(f"Created ADK session: {session_id}")
    
    # Run the ADK agent
    final_response = None
    try:
        async for event in _comprehension_runner.run_async(
            user_id="golearn",
            session_id=session_id,
            new_message=message
        ):
            # Log each agent event
            if hasattr(event, 'author') and hasattr(event, 'content'):
                logger.info(f"\n{'-'*40}\nAgent: {event.author}\n{'-'*40}")
                if event.content:
                    content_text = str(event.content)[:500]
                    logger.info(f"Output: {content_text}...")
                final_response = event
    except Exception as e:
        logger.error(f"ADK Runner error: {e}")
        raise
    
    # Get the session to extract results from state
    session = await _session_service.get_session(
        app_name="golearn",
        user_id="golearn",
        session_id=session_id
    )
    
    # Extract results from session state
    state = session.state if session else {}
    
    exploration_result = state.get("exploration_result", {})
    engagement_result = state.get("engagement_result", {})
    application_result = state.get("application_result", {})
    
    # Parse JSON if results are strings
    if isinstance(exploration_result, str):
        exploration_result = _parse_json_response(exploration_result, "Exploration")
    if isinstance(engagement_result, str):
        engagement_result = _parse_json_response(engagement_result, "Engagement")
    if isinstance(application_result, str):
        application_result = _parse_json_response(application_result, "Application")
    
    logger.info(f"\n{'='*80}\nCOMPREHENSION COMPLETE (Session: {session_id})\n{'='*80}")
    logger.info(f"Exploration keys: {list(exploration_result.keys()) if isinstance(exploration_result, dict) else 'N/A'}")
    logger.info(f"Engagement keys: {list(engagement_result.keys()) if isinstance(engagement_result, dict) else 'N/A'}")
    logger.info(f"Application keys: {list(application_result.keys()) if isinstance(application_result, dict) else 'N/A'}")
    logger.info(f"{'='*80}\n")
    
    result = {
        "exploration": exploration_result,
        "engagement": engagement_result,
        "application": application_result
    }
    
    # Clean up uploaded file
    if uploaded_file:
        try:
            genai.delete_file(uploaded_file.name)
        except Exception:
            pass
    
    return result


async def generate_questions(
    exploration: dict,
    engagement: dict,
    application: dict,
    session_id: str
) -> list:
    """
    Generate quiz questions from comprehension results.
    (Still using direct Gemini API - retention agents to be integrated later)
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    prompt = f"""Based on the following study analysis, generate 10 quiz questions.

Include a mix of:
- Recall questions (definitions, facts)
- Understanding questions (explain concepts)
- Application questions (use in scenarios)

Exploration: {exploration}
Engagement: {engagement}
Application: {application}

Respond as a JSON array:
[
    {{
        "question": "...",
        "correct_answer": "...",
        "type": "recall|understanding|application",
        "difficulty": "easy|medium|hard",
        "concept": "which topic this tests",
        "explanation": "why this is the correct answer"
    }}
]"""

    response = model.generate_content(prompt)
    
    # Log the raw LLM response
    logger.info(f"\n{'='*80}\nQUESTION GENERATION AGENT OUTPUT (Session: {session_id})\n{'='*80}")
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"\nRaw LLM Response:\n{'-'*80}\n{response.text}\n{'-'*80}")
    
    questions = _parse_json_response(response.text)
    
    # Log parsed results
    logger.info(f"\nParsed Results:")
    logger.info(f"- Number of questions generated: {len(questions) if isinstance(questions, list) else 1}")
    logger.info(f"{'='*80}\n")
    
    if isinstance(questions, dict):
        questions = [questions]
    
    return questions if isinstance(questions, list) else []


async def evaluate_answer(
    user_answer: str,
    correct_answer: str,
    question: str,
    concept: str,
    engagement_result: dict
) -> dict:
    """
    Evaluate a user's answer and provide feedback if incorrect.
    (Still using direct Gemini API - retention agents to be integrated later)
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    prompt = f"""Evaluate if the user's answer is correct.

Question: {question}
Expected Answer: {correct_answer}
User's Answer: {user_answer}

Consider semantic equivalence - the answer doesn't need to match exactly.

Respond in JSON:
{{
    "correct": true/false,
    "explanation": "brief explanation of why"
}}"""

    response = model.generate_content(prompt)
    
    # Log the raw LLM response
    logger.info(f"\n{'='*80}\nANSWER EVALUATION AGENT OUTPUT\n{'='*80}")
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info(f"Question: {question}")
    logger.info(f"User Answer: {user_answer}")
    logger.info(f"\nRaw LLM Response:\n{'-'*80}\n{response.text}\n{'-'*80}")
    
    result = _parse_json_response(response.text)
    
    # Log parsed results
    logger.info(f"\nParsed Results:")
    logger.info(f"- Correct: {result.get('correct', False)}")
    logger.info(f"- Explanation length: {len(result.get('explanation', ''))}")
    logger.info(f"{'='*80}\n")
    
    # If incorrect, generate feedback
    if not result.get("correct", False):
        feedback_prompt = f"""The user got this question wrong:
Question: {question}
Their answer: {user_answer}
Correct answer: {correct_answer}
Concept: {concept}

Provide a brief, encouraging re-explanation of the concept.
Be supportive and use simple terms. Max 3 sentences."""

        feedback_response = model.generate_content(feedback_prompt)
        
        # Log feedback generation
        logger.info(f"\n{'='*80}\nFEEDBACK AGENT OUTPUT\n{'='*80}")
        logger.info(f"Model: {settings.GEMINI_MODEL}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Concept: {concept}")
        logger.info(f"\nRaw LLM Response:\n{'-'*80}\n{feedback_response.text}\n{'-'*80}")
        logger.info(f"{'='*80}\n")
        
        result["feedback"] = feedback_response.text
    
    return result


async def run_feynman_chat(
    user_message: str,
    session_id: str,
    study_context: dict
) -> str:
    """
    Run the Feynman Technique chat using ADK.
    
    Args:
        user_message: The message from the user teaching the concept
        session_id: Session ID (shared with study session)
        study_context: Context from Pass 1 & 2 analysis
        
    Returns:
        The response from the "Novice Student" agent
    """
    # Create or update session state with context if it's the first message
    adk_session_id = f"feynman_{session_id}"
    
    try:
        session = await _session_service.get_session(
            app_name="golearn",
            user_id="golearn",
            session_id=adk_session_id
        )
    except:
        session = None

    if not session:
        # First message - include context in state
        await _session_service.create_session(
            app_name="golearn",
            user_id="golearn",
            session_id=adk_session_id,
            state={"study_context": study_context},
        )
        logger.info(f"Created Feynman ADK session: {adk_session_id}")
    
    # Create the message content
    message = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )
    
    # Run the ADK agent
    final_response_text = ""
    try:
        async for event in _feynman_runner.run_async(
            user_id="golearn",
            session_id=adk_session_id,
            new_message=message
        ):
            # The LlmAgent should emit events with content
            if hasattr(event, 'content') and event.content:
                if isinstance(event.content, types.Content):
                    final_response_text = "".join(p.text for p in event.content.parts if p.text)
                else:
                    final_response_text = str(event.content)
    except Exception as e:
        logger.error(f"Feynman ADK Runner error: {e}")
        raise
    
    return final_response_text


async def generate_feynman_greeting(
    session_id: str,
    study_context: dict
) -> str:
    """
    Generate an initial, contextual greeting from the Feynman student.
    
    Args:
        session_id: Session ID
        study_context: Context from Pass 1 & 2 analysis
        
    Returns:
        A greeting like "Hi! I'm trying to learn about [Topic]. Can you explain [Concept] to me?"
    """
    adk_session_id = f"feynman_{session_id}"
    
    # Initialize session if needed
    try:
        session = await _session_service.get_session(
            app_name="golearn",
            user_id="golearn",
            session_id=adk_session_id
        )
    except:
        session = None

    if not session:
        await _session_service.create_session(
            app_name="golearn",
            user_id="golearn",
            session_id=adk_session_id,
            state={"study_context": study_context},
        )
    
    # Send a prompt to the agent to generate a greeting
    prompt = "Introduce yourself as a curious student who wants to learn about this topic. Based on the study_context, pick one specific concept you find most interesting or confusing and ask me to explain it simply to you."
    
    message = types.Content(
        role="user",
        parts=[types.Part(text=prompt)]
    )
    
    final_response_text = ""
    try:
        async for event in _feynman_runner.run_async(
            user_id="golearn",
            session_id=adk_session_id,
            new_message=message
        ):
            if hasattr(event, 'content') and event.content:
                if isinstance(event.content, types.Content):
                    final_response_text = "".join(p.text for p in event.content.parts if p.text)
                else:
                    final_response_text = str(event.content)
    except Exception as e:
        logger.error(f"Feynman Greeting error: {e}")
        return "Hi! I'm really curious about what you're studying. Could you explain it to me?"
    
    return final_response_text


def _parse_json_response(text: str, agent_name: str = "unknown") -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    import json
    import re
    
    original_text = text
    text = text.strip()
    
    # First, try to extract JSON from markdown code blocks anywhere in the text
    # Match ```json ... ``` or ``` ... ``` (with optional closing backticks)
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)(?:```|$)', text)
    if code_block_match:
        text = code_block_match.group(1).strip()
    else:
        # Fallback: Remove code block markers if they exist at boundaries
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    
    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract the outermost JSON object using bracket matching
    def extract_json_object(s: str) -> str | None:
        start = s.find('{')
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i, c in enumerate(s[start:], start):
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return s[start:i+1]
        return None
    
    json_str = extract_json_object(text)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON array
    array_match = re.search(r'\[[\s\S]*?\]', text)
    if array_match:
        try:
            return {"items": json.loads(array_match.group())}
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"{agent_name} JSON parse failed. Raw text: {original_text[:500]}...")
    return {"raw_response": original_text, "parse_error": True}
