"""Quality Checker Agent - Validates consensus across three passes."""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext


class QualityChecker(BaseAgent):
    """
    Custom agent that checks if all three passes have completed successfully
    and meet quality thresholds. Escalates when ready to exit the loop.
    """
    
    def __init__(self, name: str = "quality_checker"):
        super().__init__(name=name)
    
    async def _run_async_impl(
        self, 
        ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Check the quality of comprehension results and decide whether to
        continue the loop or escalate (exit).
        """
        state = ctx.session.state
        
        # Check if all three pass results exist
        exploration = state.get("exploration_result")
        engagement = state.get("engagement_result")
        application = state.get("application_result")
        
        # Track iteration count
        iteration = state.get("comprehension_iteration", 0) + 1
        state["comprehension_iteration"] = iteration
        
        # Quality checks
        all_passes_complete = all([exploration, engagement, application])
        
        # Simple quality heuristics (can be enhanced with LLM-based validation)
        quality_passed = False
        if all_passes_complete:
            # Check that each result has meaningful content
            has_exploration = bool(exploration and len(str(exploration)) > 50)
            has_engagement = bool(engagement and len(str(engagement)) > 100)
            has_application = bool(application and len(str(application)) > 100)
            
            quality_passed = has_exploration and has_engagement and has_application
        
        # Update state for tracking
        state["quality_passed"] = quality_passed
        
        # Escalate (exit loop) if quality passed or max iterations reached
        should_exit = quality_passed or iteration >= 3
        
        yield Event(
            author=self.name,
            content=f"Quality check iteration {iteration}: {'PASSED' if quality_passed else 'NEEDS_REVISION'}",
            actions=EventActions(escalate=should_exit)
        )


# Export the agent instance
quality_checker = QualityChecker(name="quality_checker")
