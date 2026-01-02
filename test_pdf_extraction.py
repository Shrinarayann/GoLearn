#!/usr/bin/env python3
"""
Test script to extract images from Networks.pdf
"""
from app.services.pdf_image_service import extract_images_from_pdf
import os

# Get the PDF path
pdf_path = os.path.join(os.path.dirname(__file__), "Networks.pdf")

print(f"Extracting images from: {pdf_path}")
print("=" * 60)

# Extract images
result = extract_images_from_pdf(
    pdf_path=pdf_path,
    min_width=100,
    min_height=100,
    deduplicate=True
)

# Print results
print("\n" + "=" * 60)
print("EXTRACTION COMPLETE")
print("=" * 60)
print(f"Total images extracted: {result['total_images_extracted']}")
print(f"Output directory: {result['output_directory']}")
print("\nExtracted images:")
print("-" * 60)

for img in result['images']:
    print(f"  • {img['filename']}")
    print(f"    - Page: {img['page']}")
    print(f"    - Size: {img['width']}x{img['height']} pixels")
    print(f"    - Format: {img['format']}")
    print(f"    - Path: {img['filepath']}")
    print()
