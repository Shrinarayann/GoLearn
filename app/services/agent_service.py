"""
Agent service.
Runs ADK agents from FastAPI endpoints.
"""

from typing import Optional
import google.generativeai as genai

from ..config import settings

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)


async def run_comprehension(
    content: str,
    session_id: str,
    pdf_url: Optional[str] = None
) -> dict:
    """
    Run the three-pass comprehension on content.
    
    This calls Gemini directly with structured prompts for each pass,
    rather than using the ADK orchestrator (simpler for API use).
    
    Args:
        content: Text content to analyze
        session_id: Session ID for tracking
        pdf_url: Optional URL to PDF file
        
    Returns:
        dict with exploration, engagement, and application results
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    # Determine what to analyze
    study_material = content if content else f"[PDF content from: {pdf_url}]"
    
    # --- Pass 1: Exploration ---
    exploration_prompt = f"""You are performing Pass 1 (Exploration) of the Three-Pass Study Method.
    
Analyze the following study material and provide:
1. Structural Overview: How is the document organized?
2. High-Level Summary: 2-3 sentence summary
3. Key Topics: List the main topics and concepts

Study Material:
{study_material}

Respond in JSON format:
{{
    "structural_overview": "...",
    "summary": "...",
    "key_topics": ["topic1", "topic2", ...],
    "visual_elements": ["any diagrams or charts noted"]
}}"""

    exploration_response = model.generate_content(exploration_prompt)
    exploration_result = _parse_json_response(exploration_response.text)
    
    # --- Pass 2: Engagement ---
    engagement_prompt = f"""You are performing Pass 2 (Engagement) of the Three-Pass Study Method.
    
Based on the exploration results and the original material, provide a deep-dive analysis:
1. Detailed explanations for each key topic
2. Important definitions and formulas
3. Examples from the material

Exploration Results:
{exploration_result}

Original Material:
{study_material}

Respond in JSON format:
{{
    "concept_explanations": {{"topic1": "detailed explanation", ...}},
    "definitions": {{"term": "definition", ...}},
    "examples": ["example1", "example2", ...],
    "key_insights": ["insight1", ...]
}}"""

    engagement_response = model.generate_content(engagement_prompt)
    engagement_result = _parse_json_response(engagement_response.text)
    
    # --- Pass 3: Application ---
    application_prompt = f"""You are performing Pass 3 (Application) of the Three-Pass Study Method.
    
Synthesize the material for practical understanding:
1. Practical applications of the concepts
2. Connections to broader topics
3. Critical analysis
4. Study recommendations

Previous Analysis:
Exploration: {exploration_result}
Engagement: {engagement_result}

Respond in JSON format:
{{
    "practical_applications": ["application1", ...],
    "connections": ["connection to other topics", ...],
    "critical_analysis": "strengths and weaknesses of the material",
    "study_focus": ["areas to focus on for mastery", ...],
    "mental_models": ["memory aids or frameworks", ...]
}}"""

    application_response = model.generate_content(application_prompt)
    application_result = _parse_json_response(application_response.text)
    
    return {
        "exploration": exploration_result,
        "engagement": engagement_result,
        "application": application_result,
    }


async def generate_questions(
    exploration: dict,
    engagement: dict,
    application: dict,
    session_id: str
) -> list:
    """
    Generate quiz questions from comprehension results.
    
    Args:
        exploration: Pass 1 results
        engagement: Pass 2 results
        application: Pass 3 results
        session_id: Session ID
        
    Returns:
        List of question dicts
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
    }},
    ...
]"""

    response = model.generate_content(prompt)
    questions = _parse_json_response(response.text)
    
    # Ensure it's a list
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
    
    Args:
        user_answer: What the user answered
        correct_answer: The expected answer
        question: The question text
        concept: The concept being tested
        engagement_result: Pass 2 results for re-explanation
        
    Returns:
        dict with correct (bool) and optional feedback
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
    result = _parse_json_response(response.text)
    
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
        result["feedback"] = feedback_response.text
    
    return result


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    import json
    
    # Remove markdown code blocks if present
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
        # Return as-is in a dict if can't parse
        return {"raw_response": text}
