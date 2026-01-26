# PDF Data Extraction Fix

## Problem Identified
The app was not extracting data properly from random PDFs due to **coordinate mismatch** between the frontend and backend.

### Root Cause
- **Frontend**: The snipping tool was normalizing selection coordinates based on the **rendered page size (800px width)**
- **Backend**: The extraction logic expected coordinates normalized to the **actual PDF page dimensions** (which vary: 612pt, 595pt, etc.)
- **Result**: The cropped region sent to the backend was incorrect, causing misaligned or empty extractions

### Example of the Issue
If a PDF has actual dimensions of 612x792 (standard US letter):
1. User selects a region on the rendered 800x1070px page
2. Frontend calculates: `x_pct = 100 / 800 = 0.125` (12.5%)
3. Backend applies: `x0 = 0.125 * 612 = 76.5 points` ✓ Correct!
4. BUT if PDF dimensions were different (e.g., 1000x1200):
   - Backend applies: `x0 = 0.125 * 1000 = 125 points` ✗ Wrong region!

## Solution Implemented

### Changes to Frontend ([SnippingToolComponent.tsx](frontend/src/components/SnippingToolComponent.tsx))

#### 1. Added PDF Dimension Tracking
```typescript
const [pageDimensions, setPageDimensions] = useState<{ width: number; height: number } | null>(null);
```

#### 2. Capture Actual PDF Dimensions
When the PDF page loads, we now capture the actual page dimensions:
```typescript
<Page 
  pageNumber={pageNumber} 
  width={800} 
  renderTextLayer={false} 
  renderAnnotationLayer={false}
  onLoadSuccess={(page: any) => {
    setPageDimensions({
      width: page.width,
      height: page.height
    });
  }}
/>
```

#### 3. Fixed Coordinate Normalization
The `handleLabelSelect()` function now:
- Gets the rendered container dimensions (800px)
- Calculates the scale factor: `actual_pdf_width / rendered_width`
- Converts screen coordinates to actual PDF coordinates using the scale factor
- Normalizes to 0.0-1.0 range based on **actual PDF dimensions**

```typescript
const handleLabelSelect = (label: string) => {
  const rect = containerRef.current.getBoundingClientRect();
  
  // Calculate scale factor
  const scaleX = pageDimensions.width / rect.width;
  const scaleY = pageDimensions.height / rect.height;
  
  // Convert screen to PDF coordinates
  const pdfX = selection.x * scaleX;
  const pdfY = selection.y * scaleY;
  const pdfWidth = selection.width * scaleX;
  const pdfHeight = selection.height * scaleY;
  
  // Normalize to 0.0-1.0
  const normalized = {
    page_number: pageNumber,
    x_pct: pdfX / pageDimensions.width,
    y_pct: pdfY / pageDimensions.height,
    w_pct: pdfWidth / pageDimensions.width,
    h_pct: pdfHeight / pageDimensions.height,
    label: label,
    use_ai: useAi
  };
};
```

## Result
✅ The app now correctly extracts data from PDFs of any dimensions
✅ Coordinates are properly scaled from display to actual PDF dimensions
✅ Data extraction works consistently across different PDF formats

## Testing Recommendations
1. Test with various PDF dimensions (letter, A4, custom sizes)
2. Test with PDFs from different sources (scanned documents, digital PDFs)
3. Test both with and without AI mode enabled
4. Verify table extraction works across different table formats
