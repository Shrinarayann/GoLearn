"""Content processing tools for agents."""

from typing import Optional


def extract_key_concepts(text: str) -> dict:
    """
    Placeholder tool for extracting key concepts from text.
    In production, this would use NLP or LLM to identify concepts.
    
    Args:
        text: The text to analyze.
    
    Returns:
        dict: Contains 'status' and 'concepts' list.
    """
    # Basic keyword extraction as placeholder
    # In production, this would be handled by the LLM agents
    words = text.lower().split()
    # Filter common words (very basic stop word removal)
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                  'as', 'into', 'through', 'during', 'before', 'after', 'and',
                  'but', 'or', 'nor', 'so', 'yet', 'both', 'either', 'neither',
                  'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
                  'this', 'that', 'these', 'those', 'it', 'its'}
    
    filtered = [w for w in words if w not in stop_words and len(w) > 3]
    
    # Count frequency
    from collections import Counter
    word_counts = Counter(filtered)
    
    # Get top concepts
    top_concepts = [word for word, count in word_counts.most_common(10)]
    
    return {
        "status": "success",
        "concepts": top_concepts,
        "note": "Basic extraction - agents will perform deeper analysis"
    }


def format_study_content(
    exploration_result: dict,
    engagement_result: dict,
    application_result: dict
) -> str:
    """
    Format the three-pass results into a cohesive study guide.
    
    Args:
        exploration_result: Output from Pass 1 (overview, structure).
        engagement_result: Output from Pass 2 (deep dive, details).
        application_result: Output from Pass 3 (practical application).
    
    Returns:
        str: Formatted study content.
    """
    sections = []
    
    if exploration_result:
        sections.append("## Overview\n" + exploration_result.get("summary", ""))
        if exploration_result.get("key_topics"):
            sections.append("### Key Topics\n" + "\n".join(
                f"- {topic}" for topic in exploration_result["key_topics"]
            ))
    
    if engagement_result:
        sections.append("## Deep Dive\n" + engagement_result.get("explanation", ""))
        if engagement_result.get("diagrams"):
            sections.append("### Visual Elements\n" + engagement_result["diagrams"])
    
    if application_result:
        sections.append("## Practical Application\n" + application_result.get("applications", ""))
        if application_result.get("connections"):
            sections.append("### Broader Connections\n" + application_result["connections"])
    
    return "\n\n".join(sections)
