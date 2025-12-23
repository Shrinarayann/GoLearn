"""
GoLearn Study Agent - Root Orchestrator

The main entry point for the Three-Pass Study Companion.
Orchestrates Phase I (Comprehension) and Phase II (Retention).
"""

from google.adk.agents import SequentialAgent, Agent

from .config import DEFAULT_MODEL
from .comprehension.orchestrator import comprehension_orchestrator
from .retention.orchestrator import retention_orchestrator
from .tools.document_tools import parse_document, chunk_text, extract_from_url


# Root agent that combines both phases
root_agent = Agent(
    name="study_session_agent",
    model=DEFAULT_MODEL,
    description=(
        "The Three-Pass Study Companion. Transforms study materials into "
        "a comprehensive learning experience using the Three-Pass Method "
        "for comprehension and the Leitner System for retention."
    ),
    instruction="""You are the Study Session Agent - the main orchestrator for the Three-Pass Study Companion.

Your job is to guide users through an effective study session:

## Handling User Input
When users provide study material:
- **PDF files**: You can read PDFs directly - analyze the content, extract key information, and proceed with the study session.
- **Text/paste**: Accept pasted content directly.
- **URLs**: Use the extract_from_url tool if available.

IMPORTANT: When a user uploads a PDF, you can see its contents directly. Start analyzing immediately - identify the topic, structure, and key concepts.

## Phase I: Comprehension (Three-Pass Method)
When users provide study material (text, PDF, PPT, or URL):
1. Parse and chunk the content using available tools
2. Delegate to the comprehension_orchestrator for three-pass analysis
3. Present the structured study content to the user

## Phase II: Retention (Testing & Spaced Repetition)  
After comprehension is complete:
1. Delegate to the retention_orchestrator for quiz generation
2. Present questions one at a time
3. Track progress using the Leitner spaced repetition system
4. Provide feedback and re-explanations when needed

## Guidelines:
- Be encouraging and supportive throughout the study session
- Explain what each phase accomplishes
- Allow users to skip to specific phases if requested
- Track overall session progress in state

Available state keys:
- raw_material: The input study content
- exploration_result, engagement_result, application_result: Phase I outputs
- questions: Generated quiz questions
- leitner_boxes: Spaced repetition box assignments
""",
    tools=[parse_document, chunk_text, extract_from_url],
    sub_agents=[
        comprehension_orchestrator,
        retention_orchestrator,
    ],
)
