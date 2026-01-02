import fitz  # PyMuPDF
import base64
import io
from PIL import Image
from typing import Optional, List, Dict, Any


def _resize_image_if_needed(
    image_bytes: bytes,
    image_format: str,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 85
) -> bytes:
    """
    Resizes and compresses image if it exceeds max dimensions.
    Ensures images are always medium-sized for efficient base64 encoding.
    
    Parameters:
    - image_bytes: Original image bytes
    - image_format: Image format (jpeg, png, etc.)
    - max_width: Maximum width in pixels
    - max_height: Maximum height in pixels
    - quality: JPEG quality (1-100)
    
    Returns:
    - Optimized image bytes
    """
    try:
        # Open image from bytes
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert RGBA to RGB for JPEG
        if image_format.lower() in ['jpg', 'jpeg'] and img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Get original dimensions
        original_width, original_height = img.size
        
        # Calculate if resize is needed
        if original_width > max_width or original_height > max_height:
            # Calculate new dimensions maintaining aspect ratio
            ratio = min(max_width / original_width, max_height / original_height)
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            
            # Resize with high-quality resampling
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to bytes with compression
        output = io.BytesIO()
        save_format = 'JPEG' if image_format.lower() in ['jpg', 'jpeg'] else image_format.upper()
        
        if save_format == 'JPEG':
            img.save(output, format=save_format, quality=quality, optimize=True)
        elif save_format == 'PNG':
            img.save(output, format=save_format, optimize=True)
        else:
            img.save(output, format=save_format)
        
        return output.getvalue()
    
    except Exception as e:
        # If optimization fails, return original bytes
        print(f"Warning: Could not optimize image: {e}")
        return image_bytes


def extract_images_as_base64(
    pdf_path: str,
    min_width: int = 100,
    min_height: int = 100,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 85,
    deduplicate: bool = True
) -> Dict[str, Any]:
    """
    Extracts images from PDF and returns them as base64-encoded strings.
    Images are automatically resized/compressed to medium size for efficiency.
    Does NOT save images to disk.
    
    Parameters:
    - pdf_path: Path to PDF file
    - min_width/min_height: Filters tiny icons (default 100px)
    - max_width/max_height: Maximum dimensions for optimization (default 800px)
    - quality: JPEG compression quality 1-100 (default 85)
    - deduplicate: Avoids processing same image multiple times
    
    Returns:
    - Dict with total count and list of base64-encoded images with metadata
    """
    doc = fitz.open(pdf_path)
    
    seen_xrefs = set()
    images_data = []
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)
        
        for img_index, img in enumerate(images):
            xref = img[0]
            
            # Skip duplicates
            if deduplicate and xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            
            # Extract image
            base_image = doc.extract_image(xref)
            width = base_image["width"]
            height = base_image["height"]
            
            # Skip tiny decorative images
            if width < min_width or height < min_height:
                continue
            
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Optimize image size
            optimized_bytes = _resize_image_if_needed(
                image_bytes,
                image_ext,
                max_width=max_width,
                max_height=max_height,
                quality=quality
            )
            
            # Convert to base64
            base64_image = base64.b64encode(optimized_bytes).decode('utf-8')
            
            # Determine MIME type
            mime_type = f"image/{image_ext}" if image_ext != 'jpg' else "image/jpeg"
            
            images_data.append({
                "page": page_index + 1,
                "index": len(images_data) + 1,
                "format": image_ext,
                "original_width": width,
                "original_height": height,
                "mime_type": mime_type,
                "data_url": f"data:{mime_type};base64,{base64_image}",
                "size_kb": len(optimized_bytes) / 1024  # Size in KB
            })
    
    doc.close()
    
    return {
        "total_images": len(images_data),
        "images": images_data
    }


def extract_images_from_pdf_bytes_as_base64(
    pdf_bytes: bytes,
    min_width: int = 100,
    min_height: int = 100,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 85,
    deduplicate: bool = True
) -> Dict[str, Any]:
    """
    Extracts images from PDF bytes and returns them as base64-encoded strings.
    Useful for uploaded files. Does NOT save images to disk.
    
    Parameters:
    - pdf_bytes: PDF file content as bytes
    - min_width/min_height: Filters tiny icons (default 100px)
    - max_width/max_height: Maximum dimensions for optimization (default 800px)
    - quality: JPEG compression quality 1-100 (default 85)
    - deduplicate: Avoids processing same image multiple times
    
    Returns:
    - Dict with total count and list of base64-encoded images with metadata
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    seen_xrefs = set()
    images_data = []
    
    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)
        
        for img_index, img in enumerate(images):
            xref = img[0]
            
            # Skip duplicates
            if deduplicate and xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            
            # Extract image
            base_image = doc.extract_image(xref)
            width = base_image["width"]
            height = base_image["height"]
            
            # Skip tiny decorative images
            if width < min_width or height < min_height:
                continue
            
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Optimize image size
            optimized_bytes = _resize_image_if_needed(
                image_bytes,
                image_ext,
                max_width=max_width,
                max_height=max_height,
                quality=quality
            )
            
            # Convert to base64
            base64_image = base64.b64encode(optimized_bytes).decode('utf-8')
            
            # Determine MIME type
            mime_type = f"image/{image_ext}" if image_ext != 'jpg' else "image/jpeg"
            
            images_data.append({
                "page": page_index + 1,
                "index": len(images_data) + 1,
                "format": image_ext,
                "original_width": width,
                "original_height": height,
                "mime_type": mime_type,
                "data_url": f"data:{mime_type};base64,{base64_image}",
                "size_kb": len(optimized_bytes) / 1024  # Size in KB
            })
    
    doc.close()
    
    return {
        "total_images": len(images_data),
        "images": images_data
    }
