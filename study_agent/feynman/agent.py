"""Feynman Agent - Interactive agent for learning by teaching."""

import os
from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL

# Load instruction from prompt file
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "feynman.txt")
with open(_PROMPT_PATH, "r") as f:
    _INSTRUCTION = f.read()

feynman_agent = LlmAgent(
    name="feynman_agent",
    model=DEFAULT_MODEL,
    description=(
        "An AI agent that acts as a novice student to help users learn through "
        "the Feynman Technique. It asks questions and seeks simplifications."
    ),
    instruction=_INSTRUCTION,
)
