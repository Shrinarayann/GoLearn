"""Configuration for the Study Agent."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Model configuration
# Using gemini-2.0-flash-001 which has native PDF support
DEFAULT_MODEL = "gemini-2.0-flash-001"

# Agent configuration
MAX_COMPREHENSION_ITERATIONS = 3

# Get API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
