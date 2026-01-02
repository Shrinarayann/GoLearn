import fitz  # PyMuPDF
import os
from pathlib import Path
from typing import Optional


def extract_images_from_pdf(
    pdf_path: str,
    output_dir: Optional[str] = None,
    min_width: int = 100,
    min_height: int = 100,
    deduplicate: bool = True
) -> dict:
    """
    Extracts images from any PDF.

    Parameters:
    - pdf_path: path to PDF file
    - output_dir: folder to save images (defaults to 'images/' in project root)
    - min_width/min_height: filters tiny icons
    - deduplicate: avoids saving same image multiple times

    Returns:
    - dict with extraction statistics and saved image paths
    """
    
    # Get project root directory (2 levels up from this file)
    project_root = Path(__file__).parent.parent.parent
    
    # Default output directory in project root
    if output_dir is None:
        output_dir = os.path.join(project_root, "images")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Validate PDF path exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    doc = fitz.open(pdf_path)
    
    seen_xrefs = set()
    image_count = 0
    saved_images = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = img[0]

            if deduplicate and xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            base_image = doc.extract_image(xref)
            width = base_image["width"]
            height = base_image["height"]

            # Skip tiny decorative images
            if width < min_width or height < min_height:
                continue

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            filename = f"page{page_index+1}_img{image_count+1}.{image_ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            saved_images.append({
                "filename": filename,
                "filepath": filepath,
                "page": page_index + 1,
                "width": width,
                "height": height,
                "format": image_ext
            })

            image_count += 1
    
    doc.close()
    
    result = {
        "total_images_extracted": image_count,
        "output_directory": output_dir,
        "images": saved_images
    }
    
    print(f"Extracted {image_count} images to {output_dir}")
    
    return result


def extract_images_from_pdf_bytes(
    pdf_bytes: bytes,
    output_dir: Optional[str] = None,
    min_width: int = 100,
    min_height: int = 100,
    deduplicate: bool = True
) -> dict:
    """
    Extracts images from PDF bytes (useful for uploaded files).

    Parameters:
    - pdf_bytes: PDF file content as bytes
    - output_dir: folder to save images (defaults to 'images/' in project root)
    - min_width/min_height: filters tiny icons
    - deduplicate: avoids saving same image multiple times

    Returns:
    - dict with extraction statistics and saved image paths
    """
    
    # Get project root directory
    project_root = Path(__file__).parent.parent.parent
    
    # Default output directory in project root
    if output_dir is None:
        output_dir = os.path.join(project_root, "images")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Open PDF from bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    seen_xrefs = set()
    image_count = 0
    saved_images = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = img[0]

            if deduplicate and xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            base_image = doc.extract_image(xref)
            width = base_image["width"]
            height = base_image["height"]

            # Skip tiny decorative images
            if width < min_width or height < min_height:
                continue

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            filename = f"page{page_index+1}_img{image_count+1}.{image_ext}"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            saved_images.append({
                "filename": filename,
                "filepath": filepath,
                "page": page_index + 1,
                "width": width,
                "height": height,
                "format": image_ext
            })

            image_count += 1
    
    doc.close()
    
    result = {
        "total_images_extracted": image_count,
        "output_directory": output_dir,
        "images": saved_images
    }
    
    print(f"Extracted {image_count} images to {output_dir}")
    
    return result
