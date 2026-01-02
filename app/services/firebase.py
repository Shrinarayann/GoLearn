"""
Firebase Firestore service.
Handles all database operations.
"""

from typing import Optional, List
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

from ..config import settings

# Initialize Firebase Admin SDK
_app = None
_db = None


def get_firebase_app():
    """Get or initialize Firebase app."""
    global _app
    if _app is None:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _app = firebase_admin.initialize_app(cred, {
                'storageBucket': settings.FIREBASE_STORAGE_BUCKET
            })
        except ValueError:
            # Already initialized
            _app = firebase_admin.get_app()
    return _app


def get_firestore_client():
    """Get or initialize Firestore client (lazy loading)."""
    global _db
    if _db is None:
        get_firebase_app()
        _db = firestore.client()
    return _db


class FirestoreService:
    """Firestore database operations."""
    
    @property
    def db(self):
        """Lazy-load Firestore client."""
        return get_firestore_client()
    
    # --- Users ---
    
    async def create_user(self, user_data: dict) -> str:
        """Create a new user document."""
        user_ref = self.db.collection("users").document(user_data["user_id"])
        user_ref.set({
            **user_data,
            "created_at": datetime.utcnow(),
        })
        return user_data["user_id"]
    
    async def get_user(self, user_id: str) -> Optional[dict]:
        """Get a user by ID."""
        doc = self.db.collection("users").document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["user_id"] = doc.id
            return data
        return None
    
    async def update_user(self, user_id: str, data: dict) -> None:
        """Update a user document."""
        self.db.collection("users").document(user_id).update(data)
    
    # --- Study Sessions ---
    
    async def create_session(self, session_data: dict) -> str:
        """Create a new study session."""
        doc_ref = self.db.collection("study_sessions").document()
        session_data["session_id"] = doc_ref.id
        doc_ref.set(session_data)
        return doc_ref.id
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get a study session by ID."""
        doc = self.db.collection("study_sessions").document(session_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["session_id"] = doc.id
            return data
        return None
    
    async def get_user_sessions(self, user_id: str) -> List[dict]:
        """Get all sessions for a user."""
        docs = (
            self.db.collection("study_sessions")
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        sessions = []
        for doc in docs:
            data = doc.to_dict()
            data["session_id"] = doc.id
            sessions.append(data)
        return sessions
    
    async def update_session(self, session_id: str, data: dict) -> None:
        """Update a study session."""
        self.db.collection("study_sessions").document(session_id).update(data)
    
    async def delete_session(self, session_id: str) -> None:
        """Delete a study session."""
        self.db.collection("study_sessions").document(session_id).delete()
    
    # --- Quiz Questions ---
    
    async def create_question(self, question_data: dict) -> str:
        """Create a new quiz question."""
        doc_ref = self.db.collection("quiz_questions").document()
        question_data["question_id"] = doc_ref.id
        doc_ref.set(question_data)
        return doc_ref.id
    
    async def get_question(self, question_id: str) -> Optional[dict]:
        """Get a question by ID."""
        doc = self.db.collection("quiz_questions").document(question_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["question_id"] = doc.id
            return data
        return None
    
    async def get_session_questions(
        self, 
        session_id: str, 
        due_only: bool = False
    ) -> List[dict]:
        """Get all questions for a session."""
        query = (
            self.db.collection("quiz_questions")
            .where("session_id", "==", session_id)
        )
        
        # Note: We don't filter by date here because Firestore datetime queries
        # can be complex. Instead, we return all questions and filter in the
        # application layer (in quiz.py) based on next_review_at
        
        docs = query.stream()
        questions = []
        for doc in docs:
            data = doc.to_dict()
            data["question_id"] = doc.id
            questions.append(data)
        return questions
    
    async def get_user_questions(
        self, 
        user_id: str, 
        due_only: bool = False
    ) -> List[dict]:
        """
        Get all questions for a user across all their sessions.
        Returns questions with session metadata included.
        """
        # First, get all user sessions to build a session_id -> title map
        sessions = await self.get_user_sessions(user_id)
        session_map = {s["session_id"]: s.get("title", "Untitled") for s in sessions}
        session_ids = list(session_map.keys())
        
        if not session_ids:
            return []
        
        # Firestore has a limit of 10 items for 'in' queries, so we batch if needed
        all_questions = []
        batch_size = 10
        
        for i in range(0, len(session_ids), batch_size):
            batch_session_ids = session_ids[i:i + batch_size]
            query = (
                self.db.collection("quiz_questions")
                .where("session_id", "in", batch_session_ids)
            )
            
            docs = query.stream()
            for doc in docs:
                data = doc.to_dict()
                data["question_id"] = doc.id
                # Add session title for context
                data["session_title"] = session_map.get(data["session_id"], "Unknown")
                all_questions.append(data)
        
        return all_questions
    
    async def update_question(self, question_id: str, data: dict) -> None:
        """Update a quiz question."""
        self.db.collection("quiz_questions").document(question_id).update(data)

    # --- Quiz Concepts (SRS Tracking) ---

    async def get_concept(self, session_id: str, concept_name: str) -> Optional[dict]:
        """Get SRS tracking for a specific concept in a session."""
        docs = (
            self.db.collection("quiz_concepts")
            .where("session_id", "==", session_id)
            .where("concept_name", "==", concept_name)
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["concept_id"] = doc.id
            return data
        return None

    async def get_session_concepts(self, session_id: str) -> List[dict]:
        """Get all SRS tracked concepts for a session."""
        docs = (
            self.db.collection("quiz_concepts")
            .where("session_id", "==", session_id)
            .stream()
        )
        concepts = []
        for doc in docs:
            data = doc.to_dict()
            data["concept_id"] = doc.id
            concepts.append(data)
        return concepts

    async def create_concept(self, concept_data: dict) -> str:
        """Create SRS tracking for a concept."""
        doc_ref = self.db.collection("quiz_concepts").document()
        doc_ref.set(concept_data)
        return doc_ref.id

    async def update_concept(self, concept_id: str, data: dict) -> None:
        """Update SRS tracking for a concept."""
        self.db.collection("quiz_concepts").document(concept_id).update(data)

