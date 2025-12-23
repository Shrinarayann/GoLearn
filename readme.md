# GoLearn - Three-Pass Study Companion

An AI-powered educational platform using Google's Agent Development Kit (ADK) that implements the **Three-Pass Method** for comprehension and the **Leitner System** for long-term retention.

## 🎯 Features

- **Phase I: Comprehension** - Three-pass study method with AI agents
  - Pass 1 (Exploration): Structural overview and key topic identification
  - Pass 2 (Engagement): Deep-dive analysis with multi-modal support
  - Pass 3 (Application): Practical synthesis and broader connections

- **Phase II: Retention** - Spaced repetition with Leitner system
  - Auto-generated quiz questions
  - Smart box promotion/demotion based on answers
  - Feedback loop for re-explaining missed concepts

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google API Key or Vertex AI access

### Installation

```bash
# Clone and navigate
cd GoLearn

# Install dependencies
pip install -e .

# Set up environment
cp study_agent/.env.example study_agent/.env
# Edit .env with your GOOGLE_API_KEY
```

### Run the Agent

```bash
# Using ADK CLI
adk run study_agent

# Or with web interface
adk web
```

## 📁 Project Structure

```
GoLearn/
├── study_agent/
│   ├── __init__.py          # Exposes root_agent
│   ├── agent.py             # Main study_session_agent
│   ├── config.py            # Configuration
│   ├── comprehension/       # Phase I agents
│   │   ├── orchestrator.py  # LoopAgent for 3-pass cycle
│   │   ├── exploration_agent.py
│   │   ├── engagement_agent.py
│   │   ├── application_agent.py
│   │   └── quality_checker.py
│   ├── retention/           # Phase II agents
│   │   ├── orchestrator.py  # SequentialAgent for quiz flow
│   │   ├── testing_agent.py
│   │   ├── leitner_agent.py
│   │   └── feedback_agent.py
│   ├── tools/               # Shared tools
│   │   ├── document_tools.py
│   │   └── content_tools.py
│   └── prompts/             # Agent instructions
└── pyproject.toml
```

## 🧪 Testing

```bash
# Run tests
pytest study_agent/tests/ -v
```

## 📖 How It Works

1. **Upload Study Material** - PDF, PPT, text, or URL
2. **Three-Pass Analysis** - AI agents analyze content iteratively
3. **Study Summary** - Receive structured comprehension notes
4. **Take Quiz** - Test your understanding
5. **Track Progress** - Leitner system optimizes review schedule

## 📄 License

MIT
