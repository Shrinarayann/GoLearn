"""Leitner Agent - Manages spaced repetition box logic."""

from typing import AsyncGenerator, ClassVar

from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext


class LeitnerAgent(BaseAgent):
    """
    Implements the Leitner spaced repetition system.
    
    Box Logic:
    - Box 1: Review immediately (daily)
    - Box 2: Review every 2 days
    - Box 3: Review every 4 days
    - Box 4: Review every week
    - Box 5: Review every 2 weeks (mastered)
    
    On correct answer: Promote to next box
    On incorrect answer: Demote to Box 1
    """
    
    NUM_BOXES: ClassVar[int] = 5
    
    def __init__(self, name: str = "leitner_agent"):
        super().__init__(name=name)
    
    async def _run_async_impl(
        self, 
        ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Process user's answer and update the Leitner box state.
        
        Expected state:
        - current_question: The question being answered
        - user_answer: The user's response
        - correct_answer: The expected correct answer
        - leitner_boxes: Dict mapping concept_id -> box_number
        """
        state = ctx.session.state
        
        # Initialize boxes if not present
        if "leitner_boxes" not in state:
            state["leitner_boxes"] = {}
        
        boxes = state["leitner_boxes"]
        
        current_question = state.get("current_question", {})
        user_answer = state.get("user_answer", "")
        correct_answer = state.get("correct_answer", "")
        concept_id = current_question.get("concept", "unknown")
        
        # Simple answer comparison (can be enhanced with LLM-based evaluation)
        is_correct = self._check_answer(user_answer, correct_answer)
        
        # Get current box (default to Box 1 for new concepts)
        current_box = boxes.get(concept_id, 1)
        
        if is_correct:
            # Promote to next box (max is NUM_BOXES)
            new_box = min(current_box + 1, self.NUM_BOXES)
            message = f"✓ Correct! Concept '{concept_id}' promoted from Box {current_box} to Box {new_box}."
            needs_feedback = False
        else:
            # Demote to Box 1
            new_box = 1
            message = f"✗ Incorrect. Concept '{concept_id}' demoted to Box 1. Triggering re-explanation."
            needs_feedback = True
        
        # Update state
        boxes[concept_id] = new_box
        state["leitner_boxes"] = boxes
        state["last_answer_correct"] = is_correct
        state["needs_feedback"] = needs_feedback
        state["current_concept"] = concept_id
        
        yield Event(
            author=self.name,
            content=message,
            actions=EventActions(escalate=False)
        )
    
    def _check_answer(self, user_answer: str, correct_answer: str) -> bool:
        """
        Simple answer comparison.
        TODO: Enhance with LLM-based semantic comparison for complex answers.
        """
        # Normalize both answers
        user_normalized = user_answer.lower().strip()
        correct_normalized = correct_answer.lower().strip()
        
        # Exact match or substring match
        return (
            user_normalized == correct_normalized or
            correct_normalized in user_normalized or
            user_normalized in correct_normalized
        )


# Export the agent instance
leitner_agent = LeitnerAgent(name="leitner_agent")
