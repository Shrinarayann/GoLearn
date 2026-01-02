"""
Firebase Storage service.
Handles file uploads to Firebase Storage.
"""

from typing import Optional, List, Dict, Any
from fastapi import UploadFile
from firebase_admin import storage
from datetime import timedelta

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


async def upload_image_bytes_to_storage(
    image_bytes: bytes,
    path: str,
    content_type: str = "image/jpeg"
) -> str:
    """
    Upload image bytes to Firebase Storage and return a signed URL.
    
    Args:
        image_bytes: Raw image bytes
        path: Storage path (e.g., "sessions/123/images/image_1.jpg")
        content_type: MIME type of the image
        
    Returns:
        Signed URL with 7-day expiration (private access)
    """
    get_firebase_app()
    
    bucket = storage.bucket()
    blob = bucket.blob(path)
    
    # Check if file already exists (don't re-upload)
    if blob.exists():
        # Return a new signed URL for existing file
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(days=7),
            method="GET"
        )
    
    # Upload with content type
    blob.upload_from_string(
        image_bytes,
        content_type=content_type
    )
    
    # Generate signed URL (private - expires in 7 days)
    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(days=7),
        method="GET"
    )
    
    return signed_url


async def upload_extracted_images_to_storage(
    session_id: str,
    images: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Upload extracted images to Firebase Storage and return URLs.
    
    Args:
        session_id: Session ID for storage path
        images: List of image dicts with 'data_url' (base64) and metadata
        
    Returns:
        List of image dicts with 'firebase_url' replacing 'data_url'
    """
    import base64
    
    uploaded_images = []
    
    for idx, image in enumerate(images):
        try:
            # Extract base64 data from data URL
            data_url = image.get("data_url", "")
            if not data_url.startswith("data:"):
                continue
                
            # Parse data URL: "data:image/jpeg;base64,/9j/4AAQ..."
            header, base64_data = data_url.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
            # Determine file extension
            ext = mime_type.split("/")[1] if "/" in mime_type else "jpg"
            ext = "jpg" if ext == "jpeg" else ext
            
            # Upload to Firebase Storage
            path = f"sessions/{session_id}/images/image_{idx + 1}.{ext}"
            firebase_url = await upload_image_bytes_to_storage(
                image_bytes=image_bytes,
                path=path,
                content_type=mime_type
            )
            
            # Create new image dict with Firebase URL
            uploaded_image = {
                "index": idx,
                "page": image.get("page", 1),
                "format": ext,
                "firebase_url": firebase_url,
                "size_kb": image.get("size_kb", 0)
            }
            uploaded_images.append(uploaded_image)
            
        except Exception as e:
            print(f"Failed to upload image {idx}: {e}")
            continue
    
    return uploaded_images


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
