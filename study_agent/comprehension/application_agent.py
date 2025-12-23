"""Application Agent (Pass 3) - Practical synthesis and broader connections."""

import os
from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL

# Load instruction from prompt file
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "application.txt")
with open(_PROMPT_PATH, "r") as f:
    _INSTRUCTION = f.read()

application_agent = LlmAgent(
    name="application_agent",
    model=DEFAULT_MODEL,
    description=(
        "Pass 3 Agent: Synthesizes information for practical application, "
        "critical analysis, and connection to broader concepts."
    ),
    instruction=_INSTRUCTION,
    output_key="application_result",
)
