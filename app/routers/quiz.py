"""
Quiz and retention routes.
Handles question generation, answers, and Leitner box management.
"""

from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio

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
    stability: Optional[float] = 1.0
    fsrs_difficulty: Optional[float] = 5.0
    leitner_box: int = 1


class AnswerRequest(BaseModel):
    """Request to submit an answer."""
    answer: str


class AnswerResponse(BaseModel):
    """Answer evaluation response."""
    correct: bool
    correct_answer: str
    explanation: str
    new_stability: Optional[float] = None
    new_difficulty: Optional[float] = None
    next_review_at: Optional[datetime] = None
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


class SubmitResponse(BaseModel):
    """Response for fire-and-forget answer submission."""
    status: str
    question_id: str
    message: str


class QuestionResult(BaseModel):
    """Single question result for batch results endpoint."""
    question_id: str
    question: str
    question_type: str
    difficulty: str
    concept: str
    user_answer: str
    correct: Optional[bool] = None
    correct_answer: str
    explanation: str
    feedback: Optional[str] = None
    new_leitner_box: Optional[int] = None
    evaluation_status: str  # "pending", "completed", "failed"


class QuizResultsResponse(BaseModel):
    """Response for batch quiz results."""
    session_id: str
    total_questions: int
    evaluated_count: int
    correct_count: int
    results: List[QuestionResult]


# In-memory store for pending evaluations (for tracking)
pending_evaluations: Dict[str, asyncio.Task] = {}


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
    
    # Store whether spaced repetition is enabled for this session
    sr_enabled = session.get("enable_spaced_repetition", True)
    
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
    
    # Initialize Concepts for FSRS (only if spaced repetition is enabled)
    now = datetime.utcnow()
    if sr_enabled:
        # Extract unique concepts from the generated questions
        unique_concepts = list(set([q.get("concept", "general") for q in questions]))
        # Also add concepts from exploration if not present
        key_topics = session.get("exploration_result", {}).get("key_topics", [])
        for topic in key_topics:
            if topic not in unique_concepts:
                unique_concepts.append(topic)

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
        
        if sr_enabled:
            # Get concept data for SR-enabled sessions
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
                "next_review_at": now,  # Immediately due
                "times_reviewed": 0,
                "stability": concept_data["stability"] if concept_data else 1.0,
                "fsrs_difficulty": concept_data["difficulty"] if concept_data else 5.0
            }
        else:
            # For non-SR sessions, save with null/default tracking values
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
                "next_review_at": None,  # No review scheduling
                "times_reviewed": 0,
                "stability": None,  # No FSRS tracking
                "fsrs_difficulty": None  # No FSRS tracking
            }
        
        question_id = await db.create_question(q_data)
        saved_questions_resp.append(QuestionResponse(
            question_id=question_id,
            question=q_data["question"],
            question_type=q_data["question_type"],
            difficulty=q_data["difficulty"],
            concept=q_data["concept"],
            stability=q_data.get("stability", 1.0),
            fsrs_difficulty=q_data.get("fsrs_difficulty", 5.0),
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
    
    questions = await db.get_session_questions(session_id, due_only=False)
    
    # Check if spaced repetition is enabled for this session
    sr_enabled = session.get("enable_spaced_repetition", True)
    
    if due_only:
        # If SR is disabled, review mode should return empty
        # (SR-disabled sessions don't have scheduled reviews)
        if not sr_enabled:
            return []
        
        # Filter for due questions (consistent with dashboard logic)
        now = datetime.utcnow() + timedelta(seconds=5)
        
        due_questions = []
        for q in questions:
            review_at = q.get("next_review_at")
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
                due_questions.append(q)
        
        if not due_questions:
            return []

        # Return the due questions directly
        return [
            QuestionResponse(
                question_id=q["question_id"],
                question=q["question"],
                question_type=q.get("question_type", "recall"),
                difficulty=q.get("difficulty", "medium"),
                concept=q.get("concept", "general"),
                stability=q.get("stability"),
                fsrs_difficulty=q.get("fsrs_difficulty"),
                leitner_box=q.get("leitner_box", 1),
            )
            for q in due_questions
        ]

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
    
    # Check if spaced repetition is enabled for this session
    sr_enabled = session.get("enable_spaced_repetition", True)
    
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

    # Update Concept FSRS State (only if spaced repetition is enabled)
    if sr_enabled:
        concept_name = question.get("concept", "general")
        concept_data = await db.get_concept(question["session_id"], concept_name)
        current_box = question.get("leitner_box", 1)

        if result["correct"]:
            # Correct: promote to next box, schedule for future review
            new_box = min(current_box + 1, 5)
            
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
                    
                new_s, new_d, _ = fsrs.step(
                    stability=concept_data.get("stability", 1.0),
                    difficulty=concept_data.get("difficulty", 5.0),
                    rating=3,  # Good rating for correct
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
        else:
            # Incorrect: demote to Box 1, IMMEDIATELY due for review
            new_box = 1
            new_s = 1.0  # Reset stability
            new_d = question.get("fsrs_difficulty") or 5.0  # Keep difficulty
            next_review = datetime.utcnow()  # Immediately due!
            
            if concept_data:
                # Update concept with reset stability
                await db.update_concept(concept_data["concept_id"], {
                    "stability": new_s,
                    "last_reviewed": datetime.utcnow(),
                    "next_review_at": next_review,
                    "times_reviewed": concept_data.get("times_reviewed", 0) + 1
                })

        # Update question record with FSRS data AND next_review_at
        await db.update_question(question_id, {
            "last_reviewed": datetime.utcnow(),
            "times_reviewed": question.get("times_reviewed", 0) + 1,
            "stability": new_s,
            "fsrs_difficulty": new_d,
            "leitner_box": new_box,
            "next_review_at": next_review
        })
    else:
        # For non-SR sessions, just increment times_reviewed without FSRS updates
        new_s, new_d = None, None
        next_review = None
        await db.update_question(question_id, {
            "times_reviewed": question.get("times_reviewed", 0) + 1
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


# --- Background Evaluation Helper ---

async def evaluate_answer_background(
    question_id: str,
    user_answer: str,
    session_id: str,
    sr_enabled: bool
):
    """
    Background task to evaluate an answer and update Leitner box.
    This runs asynchronously while the user continues answering.
    """
    try:
        # Get question data
        question = await db.get_question(question_id)
        if not question:
            await db.update_question(question_id, {
                "evaluation_status": "failed",
                "evaluation_error": "Question not found"
            })
            return
        
        # Get session for context
        session = await db.get_session(session_id)
        
        # Evaluate answer using AI
        result = await evaluate_answer(
            user_answer=user_answer,
            correct_answer=question["correct_answer"],
            question=question["question"],
            concept=question.get("concept", ""),
            engagement_result=session.get("engagement_result", {}) if session else {}
        )
        
        # Handle parse errors
        if "parse_error" in result or "correct" not in result:
            await db.update_question(question_id, {
                "evaluation_status": "failed",
                "evaluation_error": "Failed to evaluate answer"
            })
            return
        
        # Update Leitner box and FSRS (same logic as submit_answer)
        if sr_enabled:
            concept_name = question.get("concept", "general")
            concept_data = await db.get_concept(session_id, concept_name)
            current_box = question.get("leitner_box", 1)
            
            if result["correct"]:
                new_box = min(current_box + 1, 5)
                
                if concept_data:
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
                    
                    new_s, new_d, _ = fsrs.step(
                        stability=concept_data.get("stability", 1.0),
                        difficulty=concept_data.get("difficulty", 5.0),
                        rating=3,
                        days_since_last_review=days_since
                    )
                    
                    next_review = datetime.utcnow() + timedelta(days=new_s)
                    
                    await db.update_concept(concept_data["concept_id"], {
                        "stability": new_s,
                        "difficulty": new_d,
                        "last_reviewed": datetime.utcnow(),
                        "next_review_at": next_review,
                        "times_reviewed": concept_data.get("times_reviewed", 0) + 1
                    })
                else:
                    new_s, new_d = 1.0, 5.0
                    next_review = datetime.utcnow() + timedelta(days=1)
            else:
                new_box = 1
                new_s = 1.0
                new_d = question.get("fsrs_difficulty") or 5.0
                next_review = datetime.utcnow()
                
                if concept_data:
                    await db.update_concept(concept_data["concept_id"], {
                        "stability": new_s,
                        "last_reviewed": datetime.utcnow(),
                        "next_review_at": next_review,
                        "times_reviewed": concept_data.get("times_reviewed", 0) + 1
                    })
            
            # Update question with evaluation results
            await db.update_question(question_id, {
                "last_reviewed": datetime.utcnow(),
                "times_reviewed": question.get("times_reviewed", 0) + 1,
                "stability": new_s,
                "fsrs_difficulty": new_d,
                "leitner_box": new_box,
                "next_review_at": next_review,
                "evaluation_status": "completed",
                "evaluated_correct": result["correct"],
                "evaluation_feedback": result.get("feedback"),
            })
        else:
            # Non-SR session
            await db.update_question(question_id, {
                "times_reviewed": question.get("times_reviewed", 0) + 1,
                "evaluation_status": "completed",
                "evaluated_correct": result["correct"],
                "evaluation_feedback": result.get("feedback"),
            })
        
        # Remove from pending evaluations
        if question_id in pending_evaluations:
            del pending_evaluations[question_id]
            
    except Exception as e:
        # Mark as failed
        try:
            await db.update_question(question_id, {
                "evaluation_status": "failed",
                "evaluation_error": str(e)
            })
        except:
            pass
        if question_id in pending_evaluations:
            del pending_evaluations[question_id]


@router.post("/questions/{question_id}/submit", response_model=SubmitResponse)
async def submit_answer_async(
    question_id: str,
    request: AnswerRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit an answer for background evaluation (fire-and-forget).
    Returns immediately while evaluation happens in background.
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
    
    sr_enabled = session.get("enable_spaced_repetition", True)
    
    # Store the user's answer immediately
    await db.update_question(question_id, {
        "user_answer": request.answer,
        "answered_at": datetime.utcnow(),
        "evaluation_status": "pending"
    })
    
    # Start background evaluation
    task = asyncio.create_task(
        evaluate_answer_background(
            question_id=question_id,
            user_answer=request.answer,
            session_id=question["session_id"],
            sr_enabled=sr_enabled
        )
    )
    pending_evaluations[question_id] = task
    
    return SubmitResponse(
        status="submitted",
        question_id=question_id,
        message="Answer submitted. Evaluation in progress."
    )


@router.get("/sessions/{session_id}/results", response_model=QuizResultsResponse)
async def get_quiz_results(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all quiz results for a session.
    Waits for pending evaluations (with timeout) then returns all results.
    """
    # Verify session
    session = await db.get_session(session_id)
    if not session or session["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Get all questions for this session
    questions = await db.get_session_questions(session_id, due_only=False)
    
    # Filter to only answered questions
    answered_questions = [q for q in questions if q.get("user_answer")]
    
    # Wait for any pending evaluations (max 15 seconds)
    pending_for_session = [
        (qid, task) for qid, task in pending_evaluations.items()
        if any(q["question_id"] == qid for q in answered_questions)
    ]
    
    if pending_for_session:
        try:
            await asyncio.wait_for(
                asyncio.gather(*[task for _, task in pending_for_session], return_exceptions=True),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            pass  # Continue with partial results
    
    # Refresh questions after waiting
    questions = await db.get_session_questions(session_id, due_only=False)
    answered_questions = [q for q in questions if q.get("user_answer")]
    
    # Build results
    results = []
    correct_count = 0
    evaluated_count = 0
    
    for q in answered_questions:
        eval_status = q.get("evaluation_status", "pending")
        is_correct = q.get("evaluated_correct")
        
        if eval_status == "completed":
            evaluated_count += 1
            if is_correct:
                correct_count += 1
        
        results.append(QuestionResult(
            question_id=q["question_id"],
            question=q["question"],
            question_type=q.get("question_type", "recall"),
            difficulty=q.get("difficulty", "medium"),
            concept=q.get("concept", "general"),
            user_answer=q.get("user_answer", ""),
            correct=is_correct,
            correct_answer=q.get("correct_answer", ""),
            explanation=q.get("explanation", ""),
            feedback=q.get("evaluation_feedback"),
            new_leitner_box=q.get("leitner_box") if eval_status == "completed" else None,
            evaluation_status=eval_status
        ))
    
    return QuizResultsResponse(
        session_id=session_id,
        total_questions=len(answered_questions),
        evaluated_count=evaluated_count,
        correct_count=correct_count,
        results=results
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


@router.get("/questions/global", response_model=List[GlobalQuestionResponse])
async def get_global_due_questions(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all questions due for review across all user's sessions.
    Questions are sorted by most overdue first (oldest next_review_at).
    """
    user_id = current_user["user_id"]
    
    # Get lightweight session summaries to filter by spaced repetition status
    all_sessions = await db.get_user_sessions_summary(user_id)
    sr_enabled_session_ids = {
        s["session_id"] for s in all_sessions 
        if s.get("enable_spaced_repetition", True)
    }
    
    # Get all questions for the user
    all_questions = await db.get_user_questions(user_id)
    
    # Filter for due questions and add timing info
    now = datetime.utcnow() + timedelta(seconds=5)
    due_questions = []
    
    for q in all_questions:
        # Skip questions from sessions with spaced repetition disabled
        if q.get("session_id") not in sr_enabled_session_ids:
            continue
            
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
    
    # Get lightweight session summaries (includes title, status, enable_spaced_repetition)
    sessions = await db.get_user_sessions_summary(user_id)
    
    if not sessions:
        return GlobalProgressResponse(
            total_due=0,
            total_concepts=0,
            overall_mastery_percentage=0.0,
            sessions_breakdown=[]
        )
    
    # Build map of SR-enabled session IDs
    sr_enabled_session_ids = {
        s["session_id"] for s in sessions 
        if s.get("enable_spaced_repetition", True)
    }
    
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
        
        # Check if due (only for SR-enabled sessions)
        if session_id not in sr_enabled_session_ids:
            # Skip due calculation for SR-disabled sessions
            continue
            
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

