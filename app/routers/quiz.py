"""
Quiz and retention routes.
Handles question generation, answers, and Leitner box management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService
from ..services.agent_service import generate_questions, evaluate_answer, generate_single_question
from ..services.fsrs import FSRS

router = APIRouter()
db = FirestoreService()
fsrs = FSRS()


# --- Schemas ---

class QuestionResponse(BaseModel):
    """Quiz question response."""
    question_id: str
    question: str
    question_type: str  # recall, understanding, application, analysis
    difficulty: str  # easy, medium, hard
    concept: str
    stability: float = 1.0
    fsrs_difficulty: float = 5.0
    leitner_box: int = 1


class AnswerRequest(BaseModel):
    """Request to submit an answer."""
    answer: str


class AnswerResponse(BaseModel):
    """Answer evaluation response."""
    correct: bool
    correct_answer: str
    explanation: str
    new_stability: float
    new_difficulty: float
    next_review_at: datetime
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
    
    # Initialize Concepts for FSRS
    # Extract unique concepts from the generated questions
    unique_concepts = list(set([q.get("concept", "general") for q in questions]))
    # Also add concepts from exploration if not present
    key_topics = session.get("exploration_result", {}).get("key_topics", [])
    for topic in key_topics:
        if topic not in unique_concepts:
            unique_concepts.append(topic)

    now = datetime.utcnow()
    for concept_name in unique_concepts:
        # Check if concept already exists
        existing_concept = await db.get_concept(session_id, concept_name)
        if not existing_concept:
            # Init FSRS stability/difficulty for "Good" (Rating 3)
            s, d, _ = fsrs.init_card(3)
            await db.create_concept({
                "session_id": session_id,
                "concept_name": concept_name,
                "stability": s,
                "difficulty": d,
                "created_at": now,
                "next_review_at": now,
                "times_reviewed": 0,
                "last_reviewed": None
            })

    # Save questions to Firestore
    saved_questions_resp = []
    for q in questions:
        concept_name = q.get("concept", "general")
        concept_data = await db.get_concept(session_id, concept_name)
        
        q_data = {
            "session_id": session_id,
            "question": q["question"],
            "correct_answer": q["correct_answer"],
            "question_type": q.get("type", "recall"),
            "difficulty": q.get("difficulty", "medium"),
            "concept": concept_name,
            "explanation": q.get("explanation", ""),
            "leitner_box": 1,
            "created_at": now,
            "next_review_at": now, # Immediately due
            "times_reviewed": 0,
            "stability": concept_data["stability"] if concept_data else 1.0,
            "fsrs_difficulty": concept_data["difficulty"] if concept_data else 5.0
        }
        question_id = await db.create_question(q_data)
        saved_questions_resp.append(QuestionResponse(
            question_id=question_id,
            question=q_data["question"],
            question_type=q_data["question_type"],
            difficulty=q_data["difficulty"],
            concept=q_data["concept"],
            stability=q_data["stability"],
            fsrs_difficulty=q_data["fsrs_difficulty"],
            leitner_box=1,
        ))
    
    # Update session status
    await db.update_session(session_id, {"status": "quizzing"})
    
    return saved_questions_resp


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
    
    if due_only:
        # 1. Find due concepts
        all_concepts = await db.get_session_concepts(session_id)
        now = datetime.utcnow() + timedelta(seconds=5)
        
        due_concepts = []
        for c in all_concepts:
            review_at = c.get("next_review_at")
            is_due = False
            if review_at is None:
                is_due = True
            elif isinstance(review_at, datetime):
                is_due = review_at.replace(tzinfo=None) <= now
            elif isinstance(review_at, str):
                try:
                    dt = datetime.fromisoformat(review_at.replace('Z', '+00:00'))
                    is_due = dt.replace(tzinfo=None) <= now
                except:
                    is_due = True
            
            if is_due:
                due_concepts.append(c)
        
        if not due_concepts:
            return []

        # 2. Generate fresh questions for due concepts
        questions_resp = []
        for concept in due_concepts:
            # Generate new question for this concept
            new_q = await generate_single_question(
                concept=concept["concept_name"],
                exploration=session.get("exploration_result", {}),
                engagement=session.get("engagement_result", {}),
                application=session.get("application_result", {})
            )
            
            # Save new question to DB
            q_data = {
                "session_id": session_id,
                "question": new_q["question"],
                "correct_answer": new_q["correct_answer"],
                "question_type": new_q.get("type", "recall"),
                "difficulty": new_q.get("difficulty", "medium"),
                "concept": concept["concept_name"],
                "explanation": new_q.get("explanation", ""),
                "leitner_box": 1,
                "created_at": now,
                "next_review_at": now,
                "times_reviewed": 0,
                "stability": concept["stability"],
                "fsrs_difficulty": concept["difficulty"],
                "is_review_instance": True
            }
            question_id = await db.create_question(q_data)
            questions_resp.append(QuestionResponse(
                question_id=question_id,
                question=q_data["question"],
                question_type=q_data["question_type"],
                difficulty=q_data["difficulty"],
                concept=q_data["concept"],
                stability=q_data["stability"],
                fsrs_difficulty=q_data["fsrs_difficulty"],
                leitner_box=1
            ))
            
        return questions_resp

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
    
    # Update Concept FSRS State
    concept_name = question.get("concept", "general")
    concept_data = await db.get_concept(question["session_id"], concept_name)
    
    if concept_data:
        # Calculate days since last review
        last_reviewed = concept_data.get("last_reviewed")
        if last_reviewed:
            if isinstance(last_reviewed, str):
                last_reviewed = datetime.fromisoformat(last_reviewed.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                last_reviewed = last_reviewed.replace(tzinfo=None)
            delta = datetime.utcnow() - last_reviewed
            days_since = max(0.1, delta.total_seconds() / 86400.0)
        else:
            days_since = 0.0
            
        rating = 3 if result["correct"] else 1  # 3=Good, 1=Again
        
        new_s, new_d, _ = fsrs.step(
            stability=concept_data.get("stability", 1.0),
            difficulty=concept_data.get("difficulty", 5.0),
            rating=rating,
            days_since_last_review=days_since
        )
        
        next_review = datetime.utcnow() + timedelta(days=new_s)
        
        # Update concept record
        await db.update_concept(concept_data["concept_id"], {
            "stability": new_s,
            "difficulty": new_d,
            "last_reviewed": datetime.utcnow(),
            "next_review_at": next_review,
            "times_reviewed": concept_data.get("times_reviewed", 0) + 1
        })
    else:
        # Fallback if concept record missing
        new_s, new_d = 1.0, 5.0
        next_review = datetime.utcnow() + timedelta(days=1)

    # Update question record
    await db.update_question(question_id, {
        "last_reviewed": datetime.utcnow(),
        "times_reviewed": question.get("times_reviewed", 0) + 1,
        "stability": new_s,
        "fsrs_difficulty": new_d
    })
    
    return AnswerResponse(
        correct=result["correct"],
        correct_answer=question["correct_answer"],
        explanation=question.get("explanation", ""),
        new_stability=new_s,
        new_difficulty=new_d,
        next_review_at=next_review,
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
    
    concepts = await db.get_session_concepts(session_id)
    
    # Calculate box distribution based on stability
    # Stability < 1d -> Box 1
    # 1d-3d -> Box 2
    # 3d-7d -> Box 3
    # 7d-14d -> Box 4
    # > 14d -> Box 5
    box_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    due_count = 0
    now = datetime.utcnow() + timedelta(seconds=5)
    
    for c in concepts:
        s = c.get("stability", 1.0)
        if s < 1: box = 1
        elif s < 3: box = 2
        elif s < 7: box = 3
        elif s < 14: box = 4
        else: box = 5
        
        box_distribution[box] += 1
        
        # Check if due
        review_at = c.get("next_review_at")
        is_due = False
        if review_at is None:
            is_due = True
        elif isinstance(review_at, datetime):
            is_due = review_at.replace(tzinfo=None) <= now
        elif isinstance(review_at, str):
             try:
                 dt = datetime.fromisoformat(review_at.replace('Z', '+00:00'))
                 is_due = dt.replace(tzinfo=None) <= now
             except:
                 is_due = True
                 
        if is_due:
            due_count += 1
    
    total = len(concepts) if concepts else 1 # Avoid div by zero
    mastered = box_distribution.get(5, 0)
    mastery_pct = (mastered / total * 100) if total > 0 else 0
    
    return ProgressResponse(
        session_id=session_id,
        total_concepts=len(concepts),
        box_distribution=box_distribution,
        mastery_percentage=round(mastery_pct, 1),
        due_for_review=due_count,
    )
