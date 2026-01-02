"""
Dashboard routes.
Optimized endpoints for dashboard data loading.
"""

from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService

router = APIRouter()
db = FirestoreService()


# --- Schemas ---

class SessionSummary(BaseModel):
    """Lightweight session summary for dashboard."""
    session_id: str
    title: str
    status: str
    created_at: datetime
    enable_spaced_repetition: bool = True  # Default True for existing sessions


class SessionProgress(BaseModel):
    """Progress stats for a session."""
    session_id: str
    due_count: int
    total: int
    mastery_percentage: float


class DashboardData(BaseModel):
    """Combined dashboard data response."""
    sessions: List[SessionSummary]
    global_progress: dict
    sessions_progress: List[SessionProgress]


# --- Routes ---

@router.get("/data", response_model=DashboardData)
async def get_dashboard_data(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all dashboard data in a single optimized request.
    Returns sessions summary, global progress, and per-session progress.
    """
    user_id = current_user["user_id"]
    
    # Get all user sessions (lightweight - no comprehension results)
    sessions = await db.get_user_sessions(user_id)
    
    # Build session summaries (only essential fields)
    session_summaries = [
        SessionSummary(
            session_id=s["session_id"],
            title=s["title"],
            status=s["status"],
            created_at=s["created_at"],
            enable_spaced_repetition=s.get("enable_spaced_repetition", True),  # Default True
        )
        for s in sessions
    ]
    
    # If no sessions, return early
    if not sessions:
        return DashboardData(
            sessions=session_summaries,
            global_progress={
                "total_due": 0,
                "total_concepts": 0,
                "overall_mastery_percentage": 0.0,
            },
            sessions_progress=[]
        )
    
    # Get all questions for the user (pass sessions to avoid duplicate query)
    session_map = {s["session_id"]: s.get("title", "Untitled") for s in sessions}
    session_ids = list(session_map.keys())
    
    # Fetch all questions in batches
    all_questions = []
    batch_size = 10
    
    for i in range(0, len(session_ids), batch_size):
        batch_session_ids = session_ids[i:i + batch_size]
        query = (
            db.db.collection("quiz_questions")
            .where("session_id", "in", batch_session_ids)
        )
        
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            data["question_id"] = doc.id
            data["session_title"] = session_map.get(data["session_id"], "Unknown")
            all_questions.append(data)
    
    # Calculate global and per-session stats in a single pass
    total_concepts = len(all_questions)
    total_due = 0
    total_mastered = 0
    now = datetime.utcnow() + timedelta(seconds=5)
    
    # Build per-session stats
    session_stats = {}
    for session_id in session_ids:
        session_stats[session_id] = {
            "session_id": session_id,
            "due_count": 0,
            "total": 0,
            "mastered": 0,
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
    
    # Build per-session progress list
    sessions_progress = []
    for stats in session_stats.values():
        if stats["total"] > 0:
            mastery_pct = (stats["mastered"] / stats["total"] * 100) if stats["total"] > 0 else 0
            sessions_progress.append(SessionProgress(
                session_id=stats["session_id"],
                due_count=stats["due_count"],
                total=stats["total"],
                mastery_percentage=round(mastery_pct, 1)
            ))
    
    return DashboardData(
        sessions=session_summaries,
        global_progress={
            "total_due": total_due,
            "total_concepts": total_concepts,
            "overall_mastery_percentage": round(overall_mastery, 1),
        },
        sessions_progress=sessions_progress
    )
