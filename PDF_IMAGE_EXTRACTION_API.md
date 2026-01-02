# PDF Image Extraction API

## Endpoint: Extract Images from PDF

**POST** `/study/sessions/{session_id}/extract-images`

Extracts images from an uploaded PDF and returns them as base64-encoded data URLs. Images are automatically optimized to medium size for efficient transmission to the frontend.

### Features
✅ **No local storage** - Images are processed in-memory and returned directly  
✅ **Automatic optimization** - Images resized to max 800x800px with quality compression  
✅ **Filters tiny images** - Ignores decorative icons (< 100x100px by default)  
✅ **Deduplication** - Prevents duplicate images from being processed  
✅ **Base64 encoded** - Ready to use in `<img>` tags with data URLs  

### Request

**Headers:**
```
Authorization: Bearer {jwt_token}
Content-Type: multipart/form-data
```

**Query Parameters:**
- `min_width` (optional, default: 100) - Minimum width in pixels to filter icons
- `min_height` (optional, default: 100) - Minimum height in pixels to filter icons
- `max_width` (optional, default: 800) - Maximum width for optimization
- `max_height` (optional, default: 800) - Maximum height for optimization
- `quality` (optional, default: 85) - JPEG compression quality (1-100)

**Body:**
- `file` (required) - PDF file to extract images from

### Response

```json
{
  "session_id": "abc123",
  "filename": "Networks.pdf",
  "total_images": 8,
  "images": [
    {
      "page": 1,
      "index": 1,
      "format": "jpeg",
      "original_width": 619,
      "original_height": 333,
      "mime_type": "image/jpeg",
      "data_url": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
      "size_kb": 23.99
    }
  ]
}
```

### Frontend Usage (React/Next.js)

```typescript
// Upload and extract images
const extractImages = async (sessionId: string, pdfFile: File) => {
  const formData = new FormData();
  formData.append('file', pdfFile);

  const response = await fetch(
    `/api/study/sessions/${sessionId}/extract-images`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    }
  );

  const data = await response.json();
  return data;
};

// Display images in React
const ImageGallery = ({ images }) => {
  return (
    <div className="grid grid-cols-2 gap-4">
      {images.map((img) => (
        <div key={img.index} className="border rounded-lg p-4">
          <img 
            src={img.data_url} 
            alt={`Page ${img.page} - Image ${img.index}`}
            className="w-full h-auto"
          />
          <p className="text-sm text-gray-600 mt-2">
            Page {img.page} • {img.original_width}×{img.original_height}px • {img.size_kb.toFixed(2)} KB
          </p>
        </div>
      ))}
    </div>
  );
};
```

### Example cURL Request

```bash
curl -X POST "http://localhost:8000/study/sessions/abc123/extract-images" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@Networks.pdf" \
  -F "max_width=800" \
  -F "max_height=800" \
  -F "quality=85"
```

### Performance Notes

- **Average image size:** ~13 KB per image (optimized)
- **8 images from Networks.pdf:** ~105 KB total
- **Base64 overhead:** ~33% increase in size (already included)
- **Recommended for:** Up to 50 images per PDF
- **Large PDFs:** Consider pagination or lazy loading in frontend

### Error Responses

**404 Not Found**
```json
{
  "detail": "Session not found"
}
```

**400 Bad Request**
```json
{
  "detail": "Only PDF files are supported"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Image extraction failed: {error_message}"
}
```

### Integration with Engagement Agent (Multi-modal Analysis)

The extracted images can be sent to Google Gemini Vision for diagram interpretation:

```python
# In engagement_agent.py
async def analyze_material_with_images(pdf_path: str):
    # Extract images
    images = extract_images_as_base64(pdf_path)
    
    # Send to Gemini for interpretation
    for img in images['images']:
        interpretation = await gemini_vision.interpret(
            image_data=img['data_url'],
            prompt=f"Explain this diagram from page {img['page']}"
        )
```

This enables the **Engagement Agent (Pass 2)** to perform true multi-modal extraction and explanation of diagrams, charts, and visual content in study materials.
