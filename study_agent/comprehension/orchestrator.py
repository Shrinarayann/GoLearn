"""Comprehension Orchestrator - LoopAgent managing the three-pass method."""

from google.adk.agents import LoopAgent

from ..config import MAX_COMPREHENSION_ITERATIONS
from .exploration_agent import exploration_agent
from .engagement_agent import engagement_agent
from .application_agent import application_agent
from .quality_checker import quality_checker

# The comprehension orchestrator runs the three passes in a loop
# until the quality checker signals completion (escalates)
comprehension_orchestrator = LoopAgent(
    name="comprehension_orchestrator",
    description=(
        "Orchestrates the Three-Pass Study Method. Runs exploration, engagement, "
        "and application agents in sequence, looping until quality standards are met."
    ),
    max_iterations=MAX_COMPREHENSION_ITERATIONS,
    sub_agents=[
        exploration_agent,
        engagement_agent,
        application_agent,
        quality_checker,
    ],
)
