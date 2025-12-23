"""Document parsing and text extraction tools for agents."""

from typing import Optional


def parse_document(file_path: str, file_type: Optional[str] = None) -> dict:
    """
    Parse a document (PDF, PPT, or text) and extract its content.
    
    Args:
        file_path: Path to the document file.
        file_type: Optional file type override ('pdf', 'ppt', 'txt').
                   If not provided, inferred from file extension.
    
    Returns:
        dict: Contains 'status', 'content' (extracted text), 
              and optionally 'images' (for multi-modal content).
    """
    import os
    
    if file_type is None:
        _, ext = os.path.splitext(file_path)
        file_type = ext.lower().lstrip('.')
    
    try:
        if file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "status": "success",
                "content": content,
                "file_type": "text"
            }
        elif file_type == 'pdf':
            # TODO: Implement PDF parsing with PyPDF2 or pdfplumber
            return {
                "status": "success",
                "content": f"[PDF content from {file_path}]",
                "file_type": "pdf",
                "note": "PDF parsing not yet implemented - using placeholder"
            }
        elif file_type in ('ppt', 'pptx'):
            # TODO: Implement PPT parsing with python-pptx
            return {
                "status": "success", 
                "content": f"[PPT content from {file_path}]",
                "file_type": "ppt",
                "note": "PPT parsing not yet implemented - using placeholder"
            }
        else:
            return {
                "status": "error",
                "error_message": f"Unsupported file type: {file_type}"
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e)
        }


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks for LLM processing.
    
    Args:
        text: The text to chunk.
        chunk_size: Maximum characters per chunk.
        overlap: Number of overlapping characters between chunks.
    
    Returns:
        list[str]: List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break
            paragraph_break = text.rfind('\n\n', start, end)
            if paragraph_break > start + chunk_size // 2:
                end = paragraph_break + 2
            else:
                # Look for sentence break
                for sep in ['. ', '! ', '? ', '\n']:
                    sentence_break = text.rfind(sep, start, end)
                    if sentence_break > start + chunk_size // 2:
                        end = sentence_break + len(sep)
                        break
        
        chunks.append(text[start:end].strip())
        start = end - overlap
    
    return chunks


def extract_from_url(url: str) -> dict:
    """
    Extract text content from a web URL.
    
    Args:
        url: The URL to extract content from.
    
    Returns:
        dict: Contains 'status' and 'content' or 'error_message'.
    """
    # TODO: Implement web scraping with requests + BeautifulSoup
    return {
        "status": "success",
        "content": f"[Web content from {url}]",
        "note": "URL extraction not yet implemented - using placeholder"
    }
