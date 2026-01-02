"""Comprehension Orchestrator - SequentialAgent running the three-pass method."""

from google.adk.agents import SequentialAgent

from .exploration_agent import exploration_agent
from .engagement_agent import engagement_agent
from .application_agent import application_agent

# The comprehension orchestrator runs the three passes in sequence
# Each agent stores its result in session state using output_key
comprehension_orchestrator = SequentialAgent(
    name="comprehension_orchestrator",
    description=(
        "Orchestrates the Three-Pass Study Method. Runs exploration, engagement, "
        "and application agents in sequence to analyze study material."
    ),
    sub_agents=[
        exploration_agent,
        engagement_agent,
        application_agent,
    ],
)
