# Agent LLM Output Logging

## Overview
All LLM agent outputs are now logged with comprehensive details for debugging and monitoring.

## Log Location
- **File**: `logs/agent_outputs.log`
- **Console**: Also displayed in terminal output
- **Format**: Timestamped structured logs with clear section separators

## What Gets Logged

### 1. Comprehension Agent (3-Pass Analysis)
Logs when exploration, engagement, and application passes run together:

```
================================================================================
COMPREHENSION AGENT OUTPUT (Session: abc123)
================================================================================
Model: gemini-1.5-flash-002
Timestamp: 2025-12-30T10:30:45.123456
Content length: 2500 chars
Has PDF: True

Raw LLM Response:
--------------------------------------------------------------------------------
{
  "exploration": {...},
  "engagement": {...},
  "application": {...}
}
--------------------------------------------------------------------------------

Parsed Results:
- Exploration keys: ['structural_overview', 'summary', 'key_topics', 'visual_elements']
- Engagement keys: ['concept_explanations', 'definitions', 'examples', 'key_insights', ...]
- Application keys: ['practical_applications', 'connections', 'critical_analysis', ...]
================================================================================
```

### 2. Question Generation Agent
Logs when quiz questions are generated:

```
================================================================================
QUESTION GENERATION AGENT OUTPUT (Session: abc123)
================================================================================
Model: gemini-1.5-flash-002
Timestamp: 2025-12-30T10:31:12.789012

Raw LLM Response:
--------------------------------------------------------------------------------
[
  {
    "question": "What is...",
    "correct_answer": "...",
    "type": "recall",
    ...
  }
]
--------------------------------------------------------------------------------

Parsed Results:
- Number of questions generated: 10
================================================================================
```

### 3. Answer Evaluation Agent
Logs when student answers are evaluated:

```
================================================================================
ANSWER EVALUATION AGENT OUTPUT
================================================================================
Model: gemini-1.5-flash-002
Timestamp: 2025-12-30T10:32:05.345678
Question: What is photosynthesis?
User Answer: Process plants use to make food from sunlight

Raw LLM Response:
--------------------------------------------------------------------------------
{
  "correct": true,
  "explanation": "Correct! Photosynthesis is indeed..."
}
--------------------------------------------------------------------------------

Parsed Results:
- Correct: True
- Explanation length: 85
================================================================================
```

### 4. Feedback Agent
Logs when re-explanations are provided for incorrect answers:

```
================================================================================
FEEDBACK AGENT OUTPUT
================================================================================
Model: gemini-1.5-flash-002
Timestamp: 2025-12-30T10:33:20.901234
Concept: Photosynthesis

Raw LLM Response:
--------------------------------------------------------------------------------
Let me help you understand photosynthesis better. Think of it as...
--------------------------------------------------------------------------------
================================================================================
```

## Log Structure

Each log entry includes:
1. **Header**: Agent type and session ID
2. **Metadata**: Model name, timestamp, input context
3. **Raw Response**: Complete unmodified LLM output
4. **Parsed Results**: Structured summary of what was extracted
5. **Footer**: Clear separation between entries

## Viewing Logs

### Real-time (Console)
Watch logs as agents run:
```bash
# Start the backend
cd /Users/shrinarayan/Desktop/GoLearn
source venv/bin/activate
uvicorn app.main:app --reload
```

### File Review
```bash
# View full log file
cat logs/agent_outputs.log

# Tail logs in real-time
tail -f logs/agent_outputs.log

# Search for specific sessions
grep "Session: abc123" logs/agent_outputs.log

# Filter by agent type
grep "COMPREHENSION AGENT" logs/agent_outputs.log
grep "QUESTION GENERATION" logs/agent_outputs.log
grep "ANSWER EVALUATION" logs/agent_outputs.log
grep "FEEDBACK AGENT" logs/agent_outputs.log
```

## Benefits

1. **Debugging**: See exactly what the LLM returned vs what was parsed
2. **Quality Monitoring**: Verify agents are generating expected outputs
3. **Performance Tracking**: Timestamps show agent execution times
4. **Error Diagnosis**: Raw responses help identify parsing issues
5. **Training Data**: Logs can inform prompt improvements

## Log Rotation

For production, consider setting up log rotation:

```python
# Add to agent_service.py if needed
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    os.path.join(logs_dir, 'agent_outputs.log'),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

## Privacy Note

Logs contain study content and student answers. Ensure:
- Secure file permissions on production servers
- Regular log cleanup policies
- Compliance with data privacy regulations
