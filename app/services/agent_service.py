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

from ..config import settings

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)


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
    
    # === SINGLE API CALL for all 3 passes to avoid rate limits ===
    combined_prompt = """You are performing the Three-Pass Study Method analysis on the provided study material.

Complete ALL THREE PASSES in your response:

## PASS 1: EXPLORATION
Analyze the structure and provide:
- Structural Overview: How is the document organized?
- High-Level Summary: 2-3 sentence summary
- Key Topics: List the main topics and concepts
- Visual Elements: Any diagrams or charts noted

## PASS 2: ENGAGEMENT  
Deep-dive analysis:
- Detailed explanations for each key topic
- Important definitions and formulas
- Examples from the material
- Key insights

## PASS 3: APPLICATION
Practical synthesis:
- Practical applications of the concepts
- Connections to broader topics
- Critical analysis (strengths/weaknesses)
- Study focus areas for mastery
- Mental models or memory aids

Respond in this exact JSON format:
{
    "exploration": {
        "structural_overview": "...",
        "summary": "...",
        "key_topics": ["topic1", "topic2"],
        "visual_elements": ["..."]
    },
    "engagement": {
        "concept_explanations": {"topic1": "explanation", "topic2": "explanation"},
        "definitions": {"term1": "definition"},
        "examples": ["example1", "example2"],
        "key_insights": ["insight1", "insight2"]
    },
    "application": {
        "practical_applications": ["application1"],
        "connections": ["connection1"],
        "critical_analysis": "strengths and weaknesses",
        "study_focus": ["focus area 1"],
        "mental_models": ["memory aid 1"]
    }
}"""

    response = model.generate_content(content_parts + [combined_prompt])
    result = _parse_json_response(response.text)
    
    # Clean up uploaded file
    if uploaded_file:
        try:
            genai.delete_file(uploaded_file.name)
        except Exception:
            pass
    
    # Extract the three sections
    if "exploration" in result and "engagement" in result and "application" in result:
        return {
            "exploration": result["exploration"],
            "engagement": result["engagement"],
            "application": result["application"],
        }
    else:
        # Fallback if structure is different
        return {
            "exploration": result.get("exploration", result),
            "engagement": result.get("engagement", {}),
            "application": result.get("application", {}),
        }


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
    questions = _parse_json_response(response.text)
    
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
