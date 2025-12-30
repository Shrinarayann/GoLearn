"""
Agent service.
Runs ADK agents from FastAPI endpoints.
"""

from typing import Optional
import google.generativeai as genai
import httpx
import tempfile
import os
import asyncio
import logging
import json
from datetime import datetime

from ..config import settings

# Import ADK agents
from study_agent.comprehension.exploration_agent import exploration_agent
from study_agent.comprehension.engagement_agent import engagement_agent
from study_agent.comprehension.application_agent import application_agent

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

# Configure Gemini (still needed for fallback/testing)
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Load agent prompts from study_agent/prompts/
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'study_agent', 'prompts')

def _load_prompt(filename: str) -> str:
    """Load prompt template from file."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, 'r') as f:
        return f.read()

# Load the actual agent prompts
EXPLORATION_PROMPT = _load_prompt('exploration.txt')
ENGAGEMENT_PROMPT = _load_prompt('engagement.txt')
APPLICATION_PROMPT = _load_prompt('application.txt')


async def run_comprehension(
    content: str,
    session_id: str,
    pdf_url: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None
) -> dict:
    """
    Run the three-pass comprehension on content.
    
    Optimized to do all 3 passes in a SINGLE API call to avoid rate limits.
    
    Args:
        content: Text content to analyze
        session_id: Session ID for tracking
        pdf_url: Optional URL to PDF file
        pdf_bytes: Optional raw PDF bytes
        
    Returns:
        dict with exploration, engagement, and application results
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    # Build content parts for multimodal input
    content_parts = []
    uploaded_file = None
    
    # If we have a PDF URL, download it
    if pdf_url and not pdf_bytes:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(pdf_url)
                if response.status_code == 200:
                    pdf_bytes = response.content
        except Exception as e:
            print(f"Failed to download PDF: {e}")
    
    # If we have PDF bytes, upload to Gemini
    if pdf_bytes:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
            content_parts.append(uploaded_file)
        finally:
            os.unlink(tmp_path)
    
    # Add text content if provided
    if content:
        content_parts.append(content)
    
    # If no content at all, error
    if not content_parts:
        raise ValueError("No content provided for analysis")
    
    logger.info(f"\n{'='*80}\nSTARTING THREE-PASS ANALYSIS (Session: {session_id})\n{'='*80}")
    logger.info(f"Model: {settings.GEMINI_MODEL}")
    logger.info(f"Content length: {len(content) if content else 0} chars")
    logger.info(f"Has PDF: {pdf_bytes is not None}")
    
    # === Run three separate agent passes using actual ADK prompts ===
    
    # PASS 1: EXPLORATION
    logger.info(f"\n{'-'*80}\nPASS 1: EXPLORATION AGENT\n{'-'*80}")
    exploration_response = model.generate_content(content_parts + [EXPLORATION_PROMPT])
    logger.info(f"Raw Response:\n{exploration_response.text}\n")
    exploration_result = _parse_json_response(exploration_response.text)
    
    # PASS 2: ENGAGEMENT (with context from exploration)
    logger.info(f"\n{'-'*80}\nPASS 2: ENGAGEMENT AGENT\n{'-'*80}")
    engagement_prompt_with_context = ENGAGEMENT_PROMPT.replace(
        "{exploration_result}", 
        json.dumps(exploration_result, indent=2)
    )
    engagement_response = model.generate_content(content_parts + [engagement_prompt_with_context])
    logger.info(f"Raw Response:\n{engagement_response.text}\n")
    engagement_result = _parse_json_response(engagement_response.text)
    
    # PASS 3: APPLICATION (with context from previous passes)
    logger.info(f"\n{'-'*80}\nPASS 3: APPLICATION AGENT\n{'-'*80}")
    application_prompt_with_context = APPLICATION_PROMPT.replace(
        "{exploration_result}",
        json.dumps(exploration_result, indent=2)
    ).replace(
        "{engagement_result}",
        json.dumps(engagement_result, indent=2)
    )
    application_response = model.generate_content(content_parts + [application_prompt_with_context])
    logger.info(f"Raw Response:\n{application_response.text}\n")
    application_result = _parse_json_response(application_response.text)
    
    # Log summary
    logger.info(f"\n{'='*80}\nCOMPREHENSION COMPLETE (Session: {session_id})\n{'='*80}")
    logger.info(f"Exploration keys: {list(exploration_result.keys())}")
    logger.info(f"Engagement keys: {list(engagement_result.keys())}")
    logger.info(f"Application keys: {list(application_result.keys())}")
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


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    import json
    
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {"raw_response": text}
