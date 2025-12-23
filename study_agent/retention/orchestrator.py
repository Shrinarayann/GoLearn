"""Retention Orchestrator - Manages the testing and spaced repetition flow."""

from google.adk.agents import SequentialAgent

from .testing_agent import testing_agent
from .leitner_agent import leitner_agent
from .feedback_agent import feedback_agent

# The retention orchestrator runs the testing phase sequentially
# Note: In a full implementation, this would include conditional logic
# to run feedback_agent only when needed (on incorrect answers)
retention_orchestrator = SequentialAgent(
    name="retention_orchestrator",
    description=(
        "Orchestrates the Testing & Retention phase. Generates questions, "
        "evaluates answers using Leitner system, and provides feedback when needed."
    ),
    sub_agents=[
        testing_agent,
        leitner_agent,
        feedback_agent,  # Will be conditionally triggered via state
    ],
)
