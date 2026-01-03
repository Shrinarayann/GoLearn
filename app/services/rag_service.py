"""
RAG Service for Vertex AI embeddings and vector search.
Handles chunking, embedding generation, and similarity search for the chatbot.
"""

import os
import json
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
import google.auth
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
import logging

logger = logging.getLogger(__name__)

# Initialize Vertex AI
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# Initialize once
_embedding_model = None


def get_embedding_model() -> TextEmbeddingModel:
    """Get or initialize the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        if GCP_PROJECT_ID:
            aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        _embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    return _embedding_model


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[Dict]:
    """
    Split text into overlapping chunks for embedding.
    
    Args:
        text: The full text to chunk
        chunk_size: Target size of each chunk in characters
        overlap: Number of overlapping characters between chunks
    
    Returns:
        List of chunk dicts with text and metadata
    """
    if not text or not text.strip():
        return []
    
    chunks = []
    start = 0
    chunk_index = 0
    
    while start < len(text):
        # Find end of chunk
        end = start + chunk_size
        
        # Try to break at sentence boundary if possible
        if end < len(text):
            # Look for sentence end within last 100 chars of chunk
            search_start = max(end - 100, start)
            last_period = text.rfind('. ', search_start, end)
            last_newline = text.rfind('\n', search_start, end)
            break_point = max(last_period, last_newline)
            if break_point > search_start:
                end = break_point + 1
        
        chunk_text = text[start:end].strip()
        
        if chunk_text:
            chunks.append({
                "chunk_index": chunk_index,
                "text": chunk_text,
                "start_char": start,
                "end_char": end,
            })
            chunk_index += 1
        
        # Move start for next chunk (with overlap)
        start = end - overlap if end < len(text) else len(text)
    
    return chunks


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using Vertex AI.
    
    Args:
        texts: List of text strings to embed
    
    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []
    
    try:
        model = get_embedding_model()
        # Vertex AI batch embedding
        embeddings = model.get_embeddings(texts)
        return [emb.values for emb in embeddings]
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise


async def generate_single_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    embeddings = await generate_embeddings([text])
    return embeddings[0] if embeddings else []


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


async def index_session_content(
    session_id: str,
    raw_content: str,
    exploration_result: dict,
    engagement_result: dict,
    application_result: dict,
    db  # FirestoreService instance
) -> int:
    """
    Index session content for RAG by chunking and embedding.
    
    Returns:
        Number of chunks indexed
    """
    logger.info(f"[RAG] Indexing content for session {session_id}")
    
    # Combine all content for chunking
    combined_content = raw_content or ""
    
    # Add analysis summaries
    if exploration_result:
        combined_content += f"\n\n=== EXPLORATION ANALYSIS ===\n"
        combined_content += f"Summary: {exploration_result.get('summary', '')}\n"
        combined_content += f"Key Topics: {', '.join(exploration_result.get('key_topics', []))}\n"
    
    if engagement_result:
        combined_content += f"\n\n=== ENGAGEMENT ANALYSIS ===\n"
        explanations = engagement_result.get('explanations', [])
        for exp in explanations[:5]:  # Limit to avoid too much content
            if isinstance(exp, dict):
                combined_content += f"- {exp.get('topic', '')}: {exp.get('explanation', '')}\n"
    
    if application_result:
        combined_content += f"\n\n=== APPLICATION ANALYSIS ===\n"
        applications = application_result.get('practical_applications', [])
        for app in applications[:5]:
            if isinstance(app, str):
                combined_content += f"- {app}\n"
    
    # Chunk the content
    chunks = chunk_text(combined_content, chunk_size=500, overlap=100)
    
    if not chunks:
        logger.warning(f"[RAG] No chunks generated for session {session_id}")
        return 0
    
    # Generate embeddings for all chunks
    chunk_texts = [c["text"] for c in chunks]
    logger.info(f"[RAG] Generating embeddings for {len(chunks)} chunks")
    
    embeddings = await generate_embeddings(chunk_texts)
    
    # Store chunks with embeddings in Firestore
    for i, chunk in enumerate(chunks):
        chunk_data = {
            "session_id": session_id,
            "chunk_index": chunk["chunk_index"],
            "text": chunk["text"],
            "embedding": embeddings[i] if i < len(embeddings) else [],
            "created_at": datetime.utcnow(),
        }
        await db.create_rag_chunk(session_id, chunk_data)
    
    logger.info(f"[RAG] Indexed {len(chunks)} chunks for session {session_id}")
    return len(chunks)


async def retrieve_relevant_chunks(
    session_id: str,
    query: str,
    db,  # FirestoreService instance
    top_k: int = 5
) -> List[Dict]:
    """
    Retrieve the most relevant chunks for a query using vector similarity.
    
    Args:
        session_id: The session to search within
        query: The user's question
        db: Firestore service instance
        top_k: Number of top results to return
    
    Returns:
        List of relevant chunk dicts with text and similarity score
    """
    # Generate embedding for query
    query_embedding = await generate_single_embedding(query)
    
    if not query_embedding:
        logger.error("[RAG] Failed to generate query embedding")
        return []
    
    # Get all chunks for this session
    chunks = await db.get_rag_chunks(session_id)
    
    if not chunks:
        logger.warning(f"[RAG] No chunks found for session {session_id}")
        return []
    
    # Calculate similarity scores
    scored_chunks = []
    for chunk in chunks:
        chunk_embedding = chunk.get("embedding", [])
        if chunk_embedding:
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            scored_chunks.append({
                "text": chunk.get("text", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "similarity": similarity,
            })
    
    # Sort by similarity and return top_k
    scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
    
    return scored_chunks[:top_k]
