"""
Exam Generator Service.
Orchestrates exam generation using Gemini for questions and optional diagram generation.
"""

import json
import logging
import asyncio
import tempfile
import os
from typing import Optional, Dict, List
from datetime import datetime

import google.generativeai as genai

from ..config import settings
from .firebase import FirestoreService
from .pdf_generator_service import generate_exam_pdf
from .storage_service import upload_file_to_storage

logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=settings.GOOGLE_API_KEY)

db = FirestoreService()


# Pydantic-style schema for exam questions
EXAM_QUESTION_SCHEMA = """
{
    "section_a": [
        {
            "question": "string - the question text",
            "marks": 2,
            "question_number": 1,
            "concept": "string - the topic/concept being tested"
        }
    ],
    "section_b": [
        {
            "question": "string - the question text",
            "marks": 6,
            "question_number": 5,
            "concept": "string - the topic/concept being tested",
            "needs_diagram": false,
            "diagram_description": "string - description for diagram generation if needs_diagram is true"
        }
    ],
    "section_c": [
        {
            "question": "string - the question text",
            "marks": 12,
            "question_number": 8,
            "concept": "string - the topic/concept being tested",
            "needs_diagram": false,
            "diagram_description": "string - description for diagram generation if needs_diagram is true"
        }
    ]
}
"""


async def generate_exam(
    session_id: str,
    sample_paper_bytes: bytes,
    user_id: str
) -> dict:
    """
    Generate an exam paper for a study session.
    
    This function:
    1. Fetches session data (comprehension results)
    2. Calls Gemini to generate structured questions
    3. Generates PDF using FPDF2
    4. Uploads PDF to Firebase Storage
    5. Updates session with PDF URL
    
    Args:
        session_id: The study session ID
        sample_paper_bytes: PDF bytes of the sample exam paper
        user_id: User ID for storage path
    
    Returns:
        dict with status and pdf_url
    """
    try:
        # Update status to generating
        await db.update_exam_status(session_id, "generating")
        
        # Fetch session data
        session = await db.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        exploration = session.get("exploration_result", {})
        engagement = session.get("engagement_result", {})
        application = session.get("application_result", {})
        session_title = session.get("title", "Examination Paper")
        
        logger.info(f"Generating exam for session: {session_id}")
        
        # Upload sample paper to Gemini
        uploaded_file = None
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(sample_paper_bytes)
            tmp_path = tmp.name
        
        try:
            uploaded_file = genai.upload_file(tmp_path, mime_type="application/pdf")
            logger.info(f"Uploaded sample paper to Gemini: {uploaded_file.name}")
        finally:
            os.unlink(tmp_path)
        
        # Generate questions using Gemini
        questions = await _generate_questions_with_gemini(
            uploaded_file=uploaded_file,
            exploration=exploration,
            engagement=engagement,
            application=application,
            session_title=session_title
        )
        
        logger.info(f"Generated {len(questions)} questions")
        
        # Clean up uploaded file
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
        
        # Generate diagrams using Gemini for questions with needs_diagram=True
        diagram_images: Dict[str, bytes] = {}
        diagram_questions = [q for q in questions if q.get('needs_diagram', False)]
        
        if diagram_questions:
            logger.info(f"Generating {len(diagram_questions)} diagrams...")
            for q in diagram_questions:
                question_num = str(q.get('question_number', 0))
                diagram_desc = q.get('diagram_description', '')
                
                if diagram_desc:
                    try:
                        image_bytes = await _generate_diagram_image(diagram_desc)
                        if image_bytes:
                            diagram_images[question_num] = image_bytes
                            logger.info(f"Generated diagram for Q{question_num}")
                    except Exception as e:
                        logger.error(f"Failed to generate diagram for Q{question_num}: {e}")
        
        # Generate PDF
        pdf_bytes = generate_exam_pdf(
            questions=questions,
            diagram_images=diagram_images,
            session_title=session_title
        )
        
        logger.info(f"Generated PDF: {len(pdf_bytes)} bytes")
        
        # Upload PDF to Firebase Storage
        pdf_filename = f"exam_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        storage_path = f"exams/{user_id}/{pdf_filename}"
        
        # Create a temporary file for upload
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        
        try:
            # Upload to Firebase Storage
            from firebase_admin import storage
            bucket = storage.bucket()
            blob = bucket.blob(storage_path)
            blob.upload_from_filename(tmp_path, content_type="application/pdf")
            
            # Make the file publicly accessible
            blob.make_public()
            pdf_url = blob.public_url
            
            logger.info(f"Uploaded PDF to Firebase Storage: {pdf_url}")
        finally:
            os.unlink(tmp_path)
        
        # Update session with success
        await db.update_exam_status(session_id, "ready", pdf_url=pdf_url)
        
        return {
            "status": "ready",
            "pdf_url": pdf_url,
            "questions_count": len(questions)
        }
        
    except Exception as e:
        logger.error(f"Exam generation failed for session {session_id}: {e}")
        await db.update_exam_status(session_id, "error", error=str(e))
        raise


async def _generate_questions_with_gemini(
    uploaded_file,
    exploration: dict,
    engagement: dict,
    application: dict,
    session_title: str
) -> List[Dict]:
    """
    Use Gemini to generate structured exam questions.
    
    Returns list of questions with section, marks, and optional diagram info.
    """
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    
    # Build context from comprehension results
    context_parts = []
    
    if exploration:
        context_parts.append(f"EXPLORATION (Overview):\n{json.dumps(exploration, indent=2)}")
    
    if engagement:
        # Summarize engagement to avoid token overflow
        engagement_summary = {
            "summary": engagement.get("summary", ""),
            "concept_explanations": engagement.get("concept_explanations", {}),
            "key_insights": engagement.get("key_insights", []),
        }
        context_parts.append(f"ENGAGEMENT (Deep Analysis):\n{json.dumps(engagement_summary, indent=2)}")
    
    if application:
        context_parts.append(f"APPLICATION (Practical):\n{json.dumps(application, indent=2)}")
    
    study_context = "\n\n".join(context_parts)
    
    prompt = f"""You are an expert exam paper generator. Based on the provided study material analysis and sample exam paper style, generate a complete examination paper.

STUDY MATERIAL CONTEXT:
{study_context}

SAMPLE EXAM PAPER:
[The uploaded PDF shows the format, style, and difficulty level to follow]

REQUIREMENTS:
1. Generate exactly 9 questions total:
   - Section A: 4 questions worth 2 marks each (short factual answers, recall-based)
   - Section B: 3 questions worth 6 marks each (conceptual, requiring explanation)
   - Section C: 2 questions worth 12 marks each (analytical, requiring detailed analysis)

2. For Section B and C:
   - ONE question in Section B should have needs_diagram=true (a question about a visual concept)
   - ONE question in Section C should have needs_diagram=true (a question requiring diagram analysis)
   - For diagram questions, provide a detailed "diagram_description" that describes what diagram should accompany the question

3. Questions should:
   - Be directly related to the study material topics
   - Match the style and difficulty of the sample paper
   - Progress from easier (Section A) to harder (Section C)
   - Test understanding, not just memorization

4. Question numbering should be continuous: 1-4 for Section A, 5-7 for Section B, 8-9 for Section C

OUTPUT FORMAT (strict JSON, no markdown):
{EXAM_QUESTION_SCHEMA}

Generate the exam questions now. Output ONLY valid JSON, no explanations."""

    # Generate content with both the uploaded file and text prompt
    # Use google.generativeai native format (not google.genai types)
    response = model.generate_content([uploaded_file, prompt])
    
    logger.info(f"Gemini response for exam generation:\n{response.text[:1000]}...")
    
    # Parse JSON response
    questions_data = _parse_json_response(response.text)
    
    # Flatten into single list with section markers
    all_questions = []
    
    for q in questions_data.get("section_a", []):
        q["section"] = "A"
        q["marks"] = 2
        q["needs_diagram"] = False
        all_questions.append(q)
    
    for q in questions_data.get("section_b", []):
        q["section"] = "B"
        q["marks"] = 6
        all_questions.append(q)
    
    for q in questions_data.get("section_c", []):
        q["section"] = "C"
        q["marks"] = 12
        all_questions.append(q)
    
    return all_questions


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    import re
    
    original_text = text
    text = text.strip()
    
    # Extract JSON from markdown code blocks
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)(?:```|$)', text)
    if code_block_match:
        text = code_block_match.group(1).strip()
    else:
        # Remove code block markers at boundaries
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    
    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON object
    start = text.find('{')
    if start != -1:
        depth = 0
        in_string = False
        escape = False
        for i, c in enumerate(text[start:], start):
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
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        break
    
    logger.warning(f"Failed to parse exam JSON. Raw text: {original_text[:500]}...")
    return {"section_a": [], "section_b": [], "section_c": [], "parse_error": True}


async def _generate_diagram_image(description: str) -> Optional[bytes]:
    """
    Generate a diagram image using Gemini's image generation model.
    
    Args:
        description: Text description of the diagram to generate
        
    Returns:
        Image bytes (PNG format) or None if generation fails
    """
    from google import genai as google_genai
    from io import BytesIO
    
    try:
        # Create client with existing API key
        client = google_genai.Client(api_key=settings.GOOGLE_API_KEY)
        
        # Generate prompt for educational diagram
        prompt = f"""Create a clear, professional educational diagram for an exam paper.
The diagram should be:
- Simple and easy to understand
- Black and white or minimal colors
- Suitable for printing
- Labeled clearly

Diagram description: {description}"""
        
        logger.info(f"Generating diagram: {description[:100]}...")
        
        # Generate image using Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=google_genai.types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        
        # Extract image from response
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                # Get image data
                image_data = part.inline_data.data
                mime_type = part.inline_data.mime_type
                
                logger.info(f"Generated image: {mime_type}, {len(image_data)} bytes")
                
                # Convert to PNG if needed
                if mime_type != "image/png":
                    from PIL import Image
                    img = Image.open(BytesIO(image_data))
                    png_buffer = BytesIO()
                    img.save(png_buffer, format="PNG")
                    return png_buffer.getvalue()
                
                return image_data
        
        logger.warning("No image found in Gemini response")
        return None
        
    except Exception as e:
        logger.error(f"Diagram generation failed: {e}")
        return None

