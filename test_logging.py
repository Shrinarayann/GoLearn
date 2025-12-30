#!/usr/bin/env python3
"""
Quick test to demonstrate agent logging.
Run this to see how logs appear.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.agent_service import logger

def demo_logging():
    """Demonstrate the logging format."""
    
    print("\n" + "="*80)
    print("AGENT LOGGING DEMO")
    print("="*80 + "\n")
    
    print("When agents run, you'll see logs like this:\n")
    
    # Simulate comprehension agent log
    logger.info(f"\n{'='*80}\nCOMPREHENSION AGENT OUTPUT (Session: demo123)\n{'='*80}")
    logger.info(f"Model: gemini-1.5-flash-002")
    logger.info(f"Timestamp: 2025-12-30T10:30:45.123456")
    logger.info(f"Content length: 2500 chars")
    logger.info(f"Has PDF: True")
    logger.info(f"\nRaw LLM Response:\n{'-'*80}")
    logger.info('{\n  "exploration": {"summary": "Demo content..."},')
    logger.info('  "engagement": {"concept_explanations": {...}},')
    logger.info('  "application": {...}\n}')
    logger.info(f"{'-'*80}")
    logger.info(f"\nParsed Results:")
    logger.info(f"- Exploration keys: ['structural_overview', 'summary', 'key_topics']")
    logger.info(f"- Engagement keys: ['concept_explanations', 'definitions', 'examples']")
    logger.info(f"- Application keys: ['practical_applications', 'connections']")
    logger.info(f"{'='*80}\n")
    
    print("\n" + "="*80)
    print("LOGS SAVED TO:")
    print("="*80)
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    log_file = os.path.join(logs_dir, 'agent_outputs.log')
    print(f"File: {log_file}")
    print("Console: stdout (what you see above)")
    print("\nTo view logs:")
    print(f"  tail -f {log_file}")
    print(f"  cat {log_file}")
    print(f'  grep "COMPREHENSION" {log_file}')
    print("="*80 + "\n")

if __name__ == "__main__":
    demo_logging()
