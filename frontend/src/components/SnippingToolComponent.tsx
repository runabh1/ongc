import React, { useState, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF Worker
if (typeof window !== 'undefined') {
  const workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;
  pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
}

interface SnippingToolProps {
  file: File;
  onExtract: (selection: any) => void;
}

export const SnippingTool: React.FC<SnippingToolProps> = ({ file, onExtract }) => {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selection, setSelection] = useState<any>(null);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [showLabelSelector, setShowLabelSelector] = useState(false);
  const [useAi, setUseAi] = useState(false);
  const [pageDimensions, setPageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [isImage, setIsImage] = useState(false);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // Detect if file is image or PDF
  React.useEffect(() => {
    const isImageFile = file.type.startsWith('image/');
    setIsImage(isImageFile);
    if (isImageFile) {
      setNumPages(1);
      setPageNumber(1);
    }
  }, [file]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!isSelecting || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setStartPos({ x, y });
    setSelection({ x, y, width: 0, height: 0 });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isSelecting || !selection || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const currX = e.clientX - rect.left;
    const currY = e.clientY - rect.top;

    setSelection({
      x: Math.min(startPos.x, currX),
      y: Math.min(startPos.y, currY),
      width: Math.abs(currX - startPos.x),
      height: Math.abs(currY - startPos.y)
    });
  };

  const handleMouseUp = () => {
    if (!isSelecting || !selection) return;
    setIsSelecting(false);
    setShowLabelSelector(true);
  };

  const handleLabelSelect = (label: string) => {
    if (!containerRef.current || !pageDimensions) return;
    
    // Get the actual rendered container dimensions
    const rect = containerRef.current.getBoundingClientRect();
    
    // Calculate scale factor between rendered page and actual dimensions
    const scaleX = pageDimensions.width / rect.width;
    const scaleY = pageDimensions.height / rect.height;
    
    // Convert screen coordinates to actual coordinates
    const actualX = selection.x * scaleX;
    const actualY = selection.y * scaleY;
    const actualWidth = selection.width * scaleX;
    const actualHeight = selection.height * scaleY;
    
    // Normalize to 0.0-1.0 range based on actual dimensions
    const normalized = {
      page_number: isImage ? 1 : pageNumber,
      x_pct: actualX / pageDimensions.width,
      y_pct: actualY / pageDimensions.height,
      w_pct: actualWidth / pageDimensions.width,
      h_pct: actualHeight / pageDimensions.height,
      label: label,
      use_ai: useAi
    };

    onExtract(normalized);
    setSelection(null);
    setShowLabelSelector(false);
  };

  const TABLE_OPTIONS = [
    "WCR_WELLHEAD", "WCR_CASING", "WCR_LOGSRECORD", 
    "WCR_DIRSRVY", "WCR_SWC", "WCR_HCSHOWS"
  ];

  return (
    <div className="flex flex-col h-full bg-gray-100">
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex justify-between items-center shadow-sm z-10">
        <div className="flex items-center space-x-3">
          {!isImage && (
            <>
              <button 
                disabled={pageNumber <= 1} 
                onClick={() => setPageNumber(p => p - 1)} 
                className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors shadow-sm"
              >
                &larr; Previous
              </button>
              <span className="text-sm text-gray-600 font-medium min-w-[100px] text-center">
                Page <span className="text-gray-900 font-bold">{pageNumber}</span> of <span className="text-gray-900 font-bold">{numPages}</span>
              </span>
              <button 
                disabled={pageNumber >= numPages} 
                onClick={() => setPageNumber(p => p + 1)} 
                className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors shadow-sm"
              >
                Next &rarr;
              </button>
            </>
          )}
          {isImage && (
            <span className="text-sm text-gray-600 font-medium px-4 py-2 bg-gray-100 rounded-lg">
              📷 Image Mode
            </span>
          )}
        </div>
        
        <button
          onClick={() => setUseAi(!useAi)}
          className={`px-4 py-2 rounded-lg font-semibold shadow-sm transition-all text-sm flex items-center gap-2 border ${useAi ? 'bg-purple-100 text-purple-700 border-purple-300' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}
        >
          {useAi ? '✨ AI Mode: ON' : '✨ AI Mode: OFF'}
        </button>

        <button 
          onClick={() => setIsSelecting(!isSelecting)}
          className={`px-5 py-2 rounded-lg font-semibold shadow-sm transition-all flex items-center gap-2 text-sm ${
            isSelecting 
              ? 'bg-red-50 text-red-600 border border-red-200 hover:bg-red-100' 
              : 'bg-blue-600 text-white hover:bg-blue-700 border border-transparent'
          }`}
        >
          {isSelecting ? 'Cancel Selection' : '✂️ Snip Region'}
        </button>
      </div>

      <div className="flex-1 overflow-auto bg-gray-100 flex justify-center p-8">
        <div 
          ref={containerRef}
          className="relative shadow-2xl border border-gray-200 bg-white"
          style={{ cursor: isSelecting ? 'crosshair' : 'default', display: 'inline-block' }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
        >
          {isImage ? (
            <img
              ref={imageRef}
              src={URL.createObjectURL(file)}
              alt="Upload preview"
              style={{ width: '800px', display: 'block' }}
              onLoad={(e) => {
                const img = e.currentTarget;
                setPageDimensions({
                  width: img.naturalWidth,
                  height: img.naturalHeight
                });
              }}
            />
          ) : (
            <Document 
              file={file} 
              onLoadSuccess={({ numPages }) => setNumPages(numPages)}
              onLoadError={(error) => console.error("Error loading PDF:", error)}
            >
              <Page 
                pageNumber={pageNumber} 
                width={800} 
                renderTextLayer={false} 
                renderAnnotationLayer={false}
                onLoadSuccess={(page: any) => {
                  // Capture actual PDF page dimensions
                  setPageDimensions({
                    width: page.width,
                    height: page.height
                  });
                }}
              />
            </Document>
          )}
          
          {selection && (
            <div style={{
              position: 'absolute',
              left: selection.x, top: selection.y,
              width: selection.width, height: selection.height,
              border: '2px solid red', backgroundColor: 'rgba(255,0,0,0.2)',
              pointerEvents: 'none'
            }} />
          )}

          {/* Label Selector Overlay */}
          {showLabelSelector && (
            <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div className="bg-white p-6 rounded-lg shadow-xl max-w-md w-full">
                <h3 className="text-lg font-bold mb-4 text-gray-800">Select Data Type</h3>
                <div className="grid grid-cols-2 gap-3">
                  {TABLE_OPTIONS.map(opt => (
                    <button 
                      key={opt}
                      onClick={() => handleLabelSelect(opt)}
                      className="px-4 py-2 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 border border-blue-200 font-medium text-sm"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
                <button 
                  onClick={() => { setShowLabelSelector(false); setSelection(null); }}
                  className="mt-4 w-full py-2 text-gray-500 hover:text-gray-700 text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};