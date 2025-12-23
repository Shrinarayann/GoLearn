"""Engagement Agent (Pass 2) - Deep dive analysis with multi-modal support."""

import os
from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL

# Load instruction from prompt file
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "engagement.txt")
with open(_PROMPT_PATH, "r") as f:
    _INSTRUCTION = f.read()

engagement_agent = LlmAgent(
    name="engagement_agent",
    model=DEFAULT_MODEL,
    description=(
        "Pass 2 Agent: Performs deep-dive analysis, explains core concepts, "
        "and interprets diagrams/charts found in the material."
    ),
    instruction=_INSTRUCTION,
    output_key="engagement_result",
)
