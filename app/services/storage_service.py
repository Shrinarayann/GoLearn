"""
Firebase Storage service.
Handles file uploads to Firebase Storage.
"""

from typing import Optional
from fastapi import UploadFile
from firebase_admin import storage

from .firebase import get_firebase_app
from ..config import settings


async def upload_file_to_storage(
    file: UploadFile,
    path: str
) -> str:
    """
    Upload a file to Firebase Storage.
    
    Args:
        file: The uploaded file
        path: Storage path (e.g., "sessions/123/doc.pdf")
        
    Returns:
        Public URL of the uploaded file
    """
    get_firebase_app()
    
    bucket = storage.bucket()
    blob = bucket.blob(path)
    
    # Read file content
    content = await file.read()
    
    # Upload with content type
    blob.upload_from_string(
        content,
        content_type=file.content_type or "application/octet-stream"
    )
    
    # Make publicly accessible (or use signed URLs for private)
    blob.make_public()
    
    return blob.public_url


async def delete_file_from_storage(path: str) -> bool:
    """
    Delete a file from Firebase Storage.
    
    Args:
        path: Storage path of the file
        
    Returns:
        True if deleted, False if not found
    """
    get_firebase_app()
    
    try:
        bucket = storage.bucket()
        blob = bucket.blob(path)
        blob.delete()
        return True
    except Exception:
        return False


async def get_file_url(path: str) -> Optional[str]:
    """
    Get the public URL for a file in storage.
    
    Args:
        path: Storage path of the file
        
    Returns:
        Public URL or None if not found
    """
    get_firebase_app()
    
    try:
        bucket = storage.bucket()
        blob = bucket.blob(path)
        if blob.exists():
            return blob.public_url
        return None
    except Exception:
        return None
