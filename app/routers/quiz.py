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


class GlobalQuestionResponse(BaseModel):
    """Global quiz question response with session context."""
    question_id: str
    question: str
    question_type: str
    difficulty: str
    concept: str
    leitner_box: int
    session_id: str
    session_title: str


class SessionBreakdown(BaseModel):
    """Per-session breakdown for global progress."""
    session_id: str
    title: str
    due_count: int
    total: int
    mastery_percentage: float


class GlobalProgressResponse(BaseModel):
    """Global study progress across all sessions."""
    total_due: int
    total_concepts: int
    overall_mastery_percentage: float
    sessions_breakdown: List[SessionBreakdown]


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
    
    # Check if spaced repetition is enabled for this session
    if not session.get("enable_spaced_repetition", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spaced repetition is disabled for this session"
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
    now = datetime.utcnow()
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
            "created_at": now,
            "next_review_at": now, # Immediately due
            "times_reviewed": 0
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
    
    # Double check due date logic just in case DB doesn't filter perfectly
    if due_only:
        # Add a small buffer (5 seconds) to handle timing precision issues
        now = datetime.utcnow() + timedelta(seconds=5)
        filtered_questions = []
        for q in questions:
            review_date = q.get("next_review_at")
            is_due = False
            
            if review_date is None:
                is_due = True
            elif isinstance(review_date, datetime):
                # Remove timezone info for comparison if present
                review_naive = review_date.replace(tzinfo=None) if review_date.tzinfo else review_date
                is_due = review_naive <= now
            elif isinstance(review_date, str):
                try:
                    dt = datetime.fromisoformat(review_date.replace('Z', '+00:00'))
                    dt_naive = dt.replace(tzinfo=None)
                    is_due = dt_naive <= now
                except:
                    is_due = True
                    
            if is_due:
                filtered_questions.append(q)
        
        questions = filtered_questions

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
    
    # Handle parse errors from LLM response
    if "parse_error" in result or "correct" not in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate answer. Please try again."
        )
    
    # Calculate new Leitner box and next review date
    current_box = question.get("leitner_box", 1)
    
    # Leitner Intervals (in days)
    # Box 1: 1 day
    # Box 2: 2 days
    # Box 3: 4 days
    # Box 4: 7 days
    # Box 5: 14 days
    intervals = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
    
    if result["correct"]:
        new_box = min(current_box + 1, 5)  # Promote, max Box 5
        # Schedule for future review based on new box
        days_to_add = intervals.get(new_box, 1)
        next_review = datetime.utcnow() + timedelta(days=days_to_add)
    else:
        new_box = 1  # Demote to Box 1
        # Incorrect answers are immediately due for review
        next_review = datetime.utcnow()
    
    # Update question
    await db.update_question(question_id, {
        "leitner_box": new_box,
        "last_reviewed": datetime.utcnow(),
        "next_review_at": next_review,
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
    due_count = 0
    # Add a small buffer (5 seconds) to handle timing precision issues
    now = datetime.utcnow() + timedelta(seconds=5)
    
    for q in questions:
        box = q.get("leitner_box", 1)
        box_distribution[box] = box_distribution.get(box, 0) + 1
        
        # Check if due
        review_date = q.get("next_review_at")
        is_due = False
        if review_date is None:
            is_due = True
        elif isinstance(review_date, datetime):
            # Remove timezone info for comparison if present
            review_naive = review_date.replace(tzinfo=None) if review_date.tzinfo else review_date
            is_due = review_naive <= now
        elif isinstance(review_date, str):
             # Basic ISO parsing
             try:
                 dt = datetime.fromisoformat(review_date.replace('Z', '+00:00'))
                 dt_naive = dt.replace(tzinfo=None)
                 is_due = dt_naive <= now
             except:
                 is_due = True # Default to due if invalid date
                 
        if is_due:
            due_count += 1
    
    total = len(questions)
    mastered = box_distribution.get(5, 0)
    mastery_pct = (mastered / total * 100) if total > 0 else 0
    
    return ProgressResponse(
        session_id=session_id,
        total_concepts=total,
        box_distribution=box_distribution,
        mastery_percentage=round(mastery_pct, 1),
        due_for_review=due_count,
    )


@router.get("/questions/global", response_model=List[GlobalQuestionResponse])
async def get_global_due_questions(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all questions due for review across all user's sessions.
    Questions are sorted by most overdue first (oldest next_review_at).
    """
    user_id = current_user["user_id"]
    
    # Get all questions for the user
    all_questions = await db.get_user_questions(user_id)
    
    # Filter for due questions and add timing info
    now = datetime.utcnow() + timedelta(seconds=5)
    due_questions = []
    
    for q in all_questions:
        review_date = q.get("next_review_at")
        is_due = False
        
        if review_date is None:
            is_due = True
            # Assign a very old date for sorting (most overdue)
            q["_sort_date"] = datetime.min
        elif isinstance(review_date, datetime):
            review_naive = review_date.replace(tzinfo=None) if review_date.tzinfo else review_date
            is_due = review_naive <= now
            q["_sort_date"] = review_naive
        elif isinstance(review_date, str):
            try:
                dt = datetime.fromisoformat(review_date.replace('Z', '+00:00'))
                dt_naive = dt.replace(tzinfo=None)
                is_due = dt_naive <= now
                q["_sort_date"] = dt_naive
            except:
                is_due = True
                q["_sort_date"] = datetime.min
        
        if is_due:
            due_questions.append(q)
    
    # Sort by most overdue first (oldest next_review_at)
    due_questions.sort(key=lambda x: x.get("_sort_date", datetime.min))
    
    return [
        GlobalQuestionResponse(
            question_id=q["question_id"],
            question=q["question"],
            question_type=q.get("question_type", "recall"),
            difficulty=q.get("difficulty", "medium"),
            concept=q.get("concept", "general"),
            leitner_box=q.get("leitner_box", 1),
            session_id=q["session_id"],
            session_title=q.get("session_title", "Unknown"),
        )
        for q in due_questions
    ]


@router.get("/progress/global", response_model=GlobalProgressResponse)
async def get_global_progress(
    current_user: dict = Depends(get_current_user)
):
    """
    Get aggregate study progress across all user's sessions.
    Shows total due count, overall mastery, and per-session breakdown.
    """
    user_id = current_user["user_id"]
    
    # Get all user sessions
    sessions = await db.get_user_sessions(user_id)
    
    if not sessions:
        return GlobalProgressResponse(
            total_due=0,
            total_concepts=0,
            overall_mastery_percentage=0.0,
            sessions_breakdown=[]
        )
    
    # Get all questions for the user
    all_questions = await db.get_user_questions(user_id)
    
    # Calculate global stats
    total_concepts = len(all_questions)
    total_due = 0
    total_mastered = 0
    now = datetime.utcnow() + timedelta(seconds=5)
    
    # Build per-session breakdown
    session_stats = {}
    for session in sessions:
        session_id = session["session_id"]
        session_stats[session_id] = {
            "session_id": session_id,
            "title": session.get("title", "Untitled"),
            "due_count": 0,
            "total": 0,
            "mastered": 0,  # Track mastered questions per session
        }
    
    # Process each question
    for q in all_questions:
        session_id = q.get("session_id")
        
        # Update session total
        if session_id in session_stats:
            session_stats[session_id]["total"] += 1
        
        # Check if mastered (box 5)
        if q.get("leitner_box", 1) == 5:
            total_mastered += 1
            if session_id in session_stats:
                session_stats[session_id]["mastered"] += 1
        
        # Check if due
        review_date = q.get("next_review_at")
        is_due = False
        
        if review_date is None:
            is_due = True
        elif isinstance(review_date, datetime):
            review_naive = review_date.replace(tzinfo=None) if review_date.tzinfo else review_date
            is_due = review_naive <= now
        elif isinstance(review_date, str):
            try:
                dt = datetime.fromisoformat(review_date.replace('Z', '+00:00'))
                dt_naive = dt.replace(tzinfo=None)
                is_due = dt_naive <= now
            except:
                is_due = True
        
        if is_due:
            total_due += 1
            if session_id in session_stats:
                session_stats[session_id]["due_count"] += 1
    
    # Calculate overall mastery percentage
    overall_mastery = (total_mastered / total_concepts * 100) if total_concepts > 0 else 0
    
    # Build breakdown list (only include sessions with questions)
    breakdown = []
    for stats in session_stats.values():
        if stats["total"] > 0:
            mastery_pct = (stats["mastered"] / stats["total"] * 100) if stats["total"] > 0 else 0
            breakdown.append(SessionBreakdown(
                session_id=stats["session_id"],
                title=stats["title"],
                due_count=stats["due_count"],
                total=stats["total"],
                mastery_percentage=round(mastery_pct, 1)
            ))
    
    return GlobalProgressResponse(
        total_due=total_due,
        total_concepts=total_concepts,
        overall_mastery_percentage=round(overall_mastery, 1),
        sessions_breakdown=breakdown,
    )

