#!/usr/bin/env python3
"""
Test the PDF image extraction service with base64 encoding
"""
from app.services.pdf_image_service import extract_images_as_base64
import json

# Test with Networks.pdf
pdf_path = "Networks.pdf"

print("Extracting images from Networks.pdf with optimization...")
print("=" * 70)

result = extract_images_as_base64(
    pdf_path=pdf_path,
    min_width=100,
    min_height=100,
    max_width=800,
    max_height=800,
    quality=85,
    deduplicate=True
)

print(f"\nTotal images extracted: {result['total_images']}")
print("\nImage details:")
print("-" * 70)

for img in result['images']:
    print(f"\n📄 Page {img['page']}, Image #{img['index']}")
    print(f"   Format: {img['format']}")
    print(f"   Original size: {img['original_width']}x{img['original_height']} pixels")
    print(f"   MIME type: {img['mime_type']}")
    print(f"   Optimized size: {img['size_kb']:.2f} KB")
    print(f"   Data URL length: {len(img['data_url'])} characters")
    print(f"   Data URL preview: {img['data_url'][:80]}...")

# Calculate total size
total_size_kb = sum(img['size_kb'] for img in result['images'])
print("\n" + "=" * 70)
print(f"Total optimized size: {total_size_kb:.2f} KB ({total_size_kb/1024:.2f} MB)")
print("✅ All images are base64-encoded and ready for JSON response!")

# Save a sample response to see the structure
with open("sample_image_response.json", "w") as f:
    # Only include the first image to keep file size reasonable
    sample = {
        "total_images": result['total_images'],
        "images": result['images'][:1] if result['images'] else []
    }
    json.dump(sample, f, indent=2)

print("\n💾 Saved sample response to sample_image_response.json")
