"""Testing Agent - Generates quiz questions from comprehension results."""

import os
from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL

# Load instruction from prompt file
_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "testing.txt")
with open(_PROMPT_PATH, "r") as f:
    _INSTRUCTION = f.read()

testing_agent = LlmAgent(
    name="testing_agent",
    model=DEFAULT_MODEL,
    description=(
        "Generates quiz questions based on the validated study content "
        "from the three-pass comprehension phase."
    ),
    instruction=_INSTRUCTION,
    output_key="questions",
)
