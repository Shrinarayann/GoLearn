"""
Dashboard routes.
Optimized endpoints for dashboard data loading.
"""

from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..dependencies import get_current_user
from ..services.firebase import FirestoreService

router = APIRouter()
db = FirestoreService()

# Thread pool for parallel Firestore queries
executor = ThreadPoolExecutor(max_workers=10)


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


def _fetch_question_stats_for_batch(session_ids: List[str], sr_enabled_sessions: set) -> dict:
    """
    Fetch only the fields needed for stats calculation (runs in thread pool).
    Returns aggregated stats for the batch.
    """
    if not session_ids:
        return {"questions": [], "stats": {}}
    
    now = datetime.utcnow() + timedelta(seconds=5)
    
    # Only fetch the 3 fields we need: session_id, leitner_box, next_review_at
    query = (
        db.db.collection("quiz_questions")
        .where("session_id", "in", session_ids)
        .select(["session_id", "leitner_box", "next_review_at"])
    )
    
    stats = {sid: {"total": 0, "mastered": 0, "due": 0} for sid in session_ids}
    
    for doc in query.stream():
        data = doc.to_dict()
        session_id = data.get("session_id")
        
        if session_id not in stats:
            continue
            
        stats[session_id]["total"] += 1
        
        # Check mastery (box 5)
        if data.get("leitner_box", 1) == 5:
            stats[session_id]["mastered"] += 1
        
        # Check if due (only for SR-enabled sessions)
        if session_id in sr_enabled_sessions:
            review_date = data.get("next_review_at")
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
                stats[session_id]["due"] += 1
    
    return stats


# --- Routes ---

@router.get("/data", response_model=DashboardData)
async def get_dashboard_data(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all dashboard data in a single optimized request.
    Uses parallel queries and field selection for maximum speed.
    """
    user_id = current_user["user_id"]
    
    # Get lightweight session summaries (excludes exploration/engagement/application results)
    sessions = await db.get_user_sessions_summary(user_id)
    
    # Build session summaries (only essential fields)
    session_summaries = [
        SessionSummary(
            session_id=s["session_id"],
            title=s["title"],
            status=s["status"],
            created_at=s["created_at"],
            enable_spaced_repetition=s.get("enable_spaced_repetition", True),
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
    
    # Build set of SR-enabled session IDs
    sr_enabled_sessions = {
        s["session_id"] for s in sessions 
        if s.get("enable_spaced_repetition", True)
    }
    
    session_ids = [s["session_id"] for s in sessions]
    
    # Split into batches of 10 (Firestore "in" query limit)
    batch_size = 10
    batches = [session_ids[i:i + batch_size] for i in range(0, len(session_ids), batch_size)]
    
    # Run all batch queries in parallel using thread pool
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, _fetch_question_stats_for_batch, batch, sr_enabled_sessions)
        for batch in batches
    ]
    
    batch_results = await asyncio.gather(*tasks)
    
    # Merge results from all batches
    all_stats = {}
    for batch_stats in batch_results:
        all_stats.update(batch_stats)
    
    # Calculate global totals
    total_concepts = sum(s["total"] for s in all_stats.values())
    total_due = sum(s["due"] for s in all_stats.values())
    total_mastered = sum(s["mastered"] for s in all_stats.values())
    
    overall_mastery = (total_mastered / total_concepts * 100) if total_concepts > 0 else 0
    
    # Build per-session progress list
    sessions_progress = [
        SessionProgress(
            session_id=session_id,
            due_count=stats["due"],
            total=stats["total"],
            mastery_percentage=round((stats["mastered"] / stats["total"] * 100) if stats["total"] > 0 else 0, 1)
        )
        for session_id, stats in all_stats.items()
        if stats["total"] > 0
    ]
    
    return DashboardData(
        sessions=session_summaries,
        global_progress={
            "total_due": total_due,
            "total_concepts": total_concepts,
            "overall_mastery_percentage": round(overall_mastery, 1),
        },
        sessions_progress=sessions_progress
    )
