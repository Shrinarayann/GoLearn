"""
Quiz and retention routes.
Handles question generation, answers, and Leitner box management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.agent_service import generate_questions, evaluate_answer

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class QuestionResponse(BaseModel):
    """Quiz question response."""
    question_id: str
    question: str
    question_type: str  # recall, understanding, application, analysis
    difficulty: str  # easy, medium, hard
    concept: str
    leitner_box: int


class AnswerRequest(BaseModel):
    """Request to submit an answer."""
    answer: str


class AnswerResponse(BaseModel):
    """Answer evaluation response."""
    correct: bool
    correct_answer: str
    explanation: str
    new_leitner_box: int
    feedback: Optional[str] = None  # Re-explanation if incorrect


class ProgressResponse(BaseModel):
    """Study progress response."""
    session_id: str
    total_concepts: int
    box_distribution: dict  # {1: 5, 2: 3, 3: 2, 4: 1, 5: 0}
    mastery_percentage: float
    due_for_review: int


# --- Routes ---

@router.post("/sessions/{session_id}/generate", response_model=List[QuestionResponse])
async def generate_quiz(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate quiz questions from the comprehension results.
    """
    # Verify session
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session["status"] not in ["ready", "quizzing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session must complete comprehension before generating quiz"
        )
    
    # If already quizzing, return existing questions
    if session["status"] == "quizzing":
        existing_questions = await db.get_session_questions(session_id)
        if existing_questions:
            return [
                QuestionResponse(
                    question_id=q["question_id"],
                    question=q["question"],
                    question_type=q.get("question_type", "recall"),
                    difficulty=q.get("difficulty", "medium"),
                    concept=q.get("concept", "general"),
                    leitner_box=q.get("leitner_box", 1),
                )
                for q in existing_questions
            ]
    
    # Generate questions using agent
    questions = await generate_questions(
        exploration=session.get("exploration_result", {}),
        engagement=session.get("engagement_result", {}),
        application=session.get("application_result", {}),
        session_id=session_id
    )
    
    # Save questions to Firestore
    saved_questions = []
    for q in questions:
        q_data = {
            "session_id": session_id,
            "question": q["question"],
            "correct_answer": q["correct_answer"],
            "question_type": q.get("type", "recall"),
            "difficulty": q.get("difficulty", "medium"),
            "concept": q.get("concept", "general"),
            "explanation": q.get("explanation", ""),
            "leitner_box": 1,  # All start in Box 1
            "created_at": datetime.utcnow(),
        }
        question_id = await db.create_question(q_data)
        saved_questions.append(QuestionResponse(
            question_id=question_id,
            question=q_data["question"],
            question_type=q_data["question_type"],
            difficulty=q_data["difficulty"],
            concept=q_data["concept"],
            leitner_box=1,
        ))
    
    # Update session status
    await db.update_session(session_id, {"status": "quizzing"})
    
    return saved_questions


@router.get("/sessions/{session_id}/questions", response_model=List[QuestionResponse])
async def get_questions(
    session_id: str,
    due_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all questions for a session.
    If due_only=True, returns only questions due for review based on Leitner schedule.
    """
    # Verify session
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    questions = await db.get_session_questions(session_id, due_only=due_only)
    
    return [
        QuestionResponse(
            question_id=q["question_id"],
            question=q["question"],
            question_type=q.get("question_type", "recall"),
            difficulty=q.get("difficulty", "medium"),
            concept=q.get("concept", "general"),
            leitner_box=q.get("leitner_box", 1),
        )
        for q in questions
    ]


@router.post("/questions/{question_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    question_id: str,
    request: AnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer to a question and update Leitner box.
    """
    # Get question
    question = await db.get_question(question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Verify ownership through session
    session = await db.get_session(question["session_id"])
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    
    # Evaluate answer
    result = await evaluate_answer(
        user_answer=request.answer,
        correct_answer=question["correct_answer"],
        question=question["question"],
        concept=question.get("concept", ""),
        engagement_result=session.get("engagement_result", {})
    )
    
    # Calculate new Leitner box
    current_box = question.get("leitner_box", 1)
    if result["correct"]:
        new_box = min(current_box + 1, 5)  # Promote, max Box 5
    else:
        new_box = 1  # Demote to Box 1
    
    # Update question
    await db.update_question(question_id, {
        "leitner_box": new_box,
        "last_reviewed": datetime.utcnow(),
        "times_reviewed": question.get("times_reviewed", 0) + 1,
    })
    
    return AnswerResponse(
        correct=result["correct"],
        correct_answer=question["correct_answer"],
        explanation=question.get("explanation", ""),
        new_leitner_box=new_box,
        feedback=result.get("feedback") if not result["correct"] else None,
    )


@router.get("/sessions/{session_id}/progress", response_model=ProgressResponse)
async def get_progress(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get study progress for a session.
    Shows Leitner box distribution and mastery percentage.
    """
    # Verify session
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    questions = await db.get_session_questions(session_id)
    
    # Calculate box distribution
    box_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for q in questions:
        box = q.get("leitner_box", 1)
        box_distribution[box] = box_distribution.get(box, 0) + 1
    
    total = len(questions)
    mastered = box_distribution.get(5, 0)
    mastery_pct = (mastered / total * 100) if total > 0 else 0
    
    # Calculate due for review (Box 1 is always due)
    due = box_distribution.get(1, 0)
    
    return ProgressResponse(
        session_id=session_id,
        total_concepts=total,
        box_distribution=box_distribution,
        mastery_percentage=round(mastery_pct, 1),
        due_for_review=due,
    )
