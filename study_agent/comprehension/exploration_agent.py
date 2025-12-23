"""Exploration Agent (Pass 1) - Structural overview and key topic identification."""

import os
from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL

# Load instruction from prompt file
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "exploration.txt")
with open(_PROMPT_PATH, "r") as f:
    _INSTRUCTION = f.read()

exploration_agent = LlmAgent(
    name="exploration_agent",
    model=DEFAULT_MODEL,
    description=(
        "Pass 1 Agent: Scans study material to generate structural overview, "
        "high-level summary, and key topic identification."
    ),
    instruction=_INSTRUCTION,
    output_key="exploration_result",
)
