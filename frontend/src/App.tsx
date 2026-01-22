import React, { useState, useEffect } from 'react';
import { SnippingTool } from './components/SnippingTool';
import { ResultsTable } from './components/ResultsTable';
import { uploadFile, extractData, exportData, saveData, downloadTemplate, exportDataAsPdf } from './api';

interface Extraction {
  id: number;
  label: string;
  sqlData: any[];
  rawData: any[];
  schema: string[];
}

const TABLE_MAP: Record<string, string> = {
  "WELL_HEADER": "WCR_WELLHEAD",
  "WCR_WELLHEAD": "WCR_WELLHEAD",
  "CASING": "WCR_CASING",
  "WCR_CASING": "WCR_CASING",
  "LOGS": "WCR_LOGSRECORD",
  "WCR_LOGSRECORD": "WCR_LOGSRECORD",
  "DIRSRVY": "WCR_DIRSRVY",
  "WCR_DIRSRVY": "WCR_DIRSRVY",
  "SWC": "WCR_SWC",
  "WCR_SWC": "WCR_SWC",
  "HCSHOWS": "WCR_HCSHOWS",
  "WCR_HCSHOWS": "WCR_HCSHOWS"
};

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadedName, setUploadedName] = useState<string>("");
  const [extractions, setExtractions] = useState<Extraction[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    console.log("App mounted successfully");
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setIsUploading(true);
      try {
        const res = await uploadFile(f);
        setUploadedName(res.filename);
        setFile(f); // Only show UI after successful upload
      } catch (err: any) {
        console.error("Upload failed", err);
        let msg = "Failed to upload file.";
        if (err.response) {
          // Server responded with a status code (e.g., 404, 500, 413)
          msg += ` Server Error: ${err.response.status} ${err.response.statusText}`;
        } else if (err.request) {
          // Request was made but no response (e.g., Network Error, Server Sleeping)
          msg += " No response from server. The backend might be waking up (wait 30s) or is unreachable.";
        } else {
          msg += ` ${err.message}`;
        }
        alert(msg);
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleExtract = async (selection: any) => {
    if (!uploadedName) return;
    try {
      const res = await extractData(uploadedName, selection);
      if (res.error) {
        alert(res.error);
      } else {
        // Append new extraction to the list instead of overwriting
        setExtractions(prev => [
          ...prev,
          {
            id: Date.now(),
            label: selection.label,
            sqlData: res.sql_data,
            rawData: res.raw_data,
            schema: res.schema || []
          }
        ]);
      }
    } catch (err) {
      console.error(err);
      alert("Extraction failed");
    }
  };

  const handleSave = async (extraction: Extraction) => {
    try {
      const res = await saveData(extraction.sqlData, TABLE_MAP[extraction.label]);
      alert(res.message);
    } catch (err: any) {
      alert("Save failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleExport = async (extraction: Extraction) => {
    await exportData(extraction.sqlData, TABLE_MAP[extraction.label]);
  };

  const handleExportPdf = async (extraction: Extraction) => {
    await exportDataAsPdf(extraction.sqlData, TABLE_MAP[extraction.label]);
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm z-30">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 text-white p-1.5 rounded-lg">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" /></svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Well Completion Data Extractor</h1>
          <button 
            onClick={() => downloadTemplate("WCR_WELLHEAD")}
            className="ml-auto text-sm text-blue-600 hover:text-blue-800 font-medium border border-blue-200 px-3 py-1 rounded hover:bg-blue-50"
          >
            Download Test PDF (Wellhead)
          </button>
        </div>
      </header>
      
      {!file ? (
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-lg w-full bg-white rounded-2xl shadow-xl p-12 text-center border border-gray-100">
            <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-3">Upload Completion Report</h2>
            <p className="text-gray-500 mb-8">Upload a PDF document to start extracting well data using the snipping tool.</p>
            
            {isUploading ? (
              <div className="flex flex-col items-center justify-center text-blue-600">
                <svg className="animate-spin h-8 w-8 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="font-medium">Uploading...</span>
              </div>
            ) : (
              <div className="relative">
                <input 
                  type="file" 
                  accept="application/pdf" 
                  onChange={handleFileChange} 
                  className="hidden"
                  id="file-upload"
                />
                <label 
                  htmlFor="file-upload"
                  className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 cursor-pointer transition-colors shadow-sm w-full sm:w-auto"
                >
                  Select PDF File
                </label>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: PDF Viewer */}
          <div className="w-2/3 border-r border-gray-200 bg-gray-100">
            <SnippingTool file={file} onExtract={handleExtract} />
          </div>
          
          {/* Right: Results */}
          <div className="w-1/3 bg-white overflow-auto p-6 border-l border-gray-200 shadow-inner">
            <h2 className="font-bold text-xl text-gray-800 mb-4 flex items-center gap-2">
              <span>📊</span> Data Validation
            </h2>
            {extractions.length > 0 && (
              <button 
                onClick={() => setExtractions([])}
                className="mb-4 text-sm text-red-600 hover:text-red-800 underline"
              >
                Clear All Results
              </button>
            )}
            {extractions.length > 0 ? (
              <div className="space-y-12">
                {extractions.map((ext) => (
                  <div key={ext.id} className="border-b border-gray-300 pb-8 last:border-0">
                    <div className="flex items-center justify-between mb-2">
                      <span className="bg-blue-100 text-blue-800 text-sm font-bold px-3 py-1 rounded-full">
                        {ext.label}
                      </span>
                    </div>
                    <ResultsTable 
                      data={ext.sqlData} 
                      rawData={ext.rawData}
                      schema={ext.schema} 
                      onExport={() => handleExport(ext)} 
                      onSave={() => handleSave(ext)}
                      onExportPdf={() => handleExportPdf(ext)}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 mt-10 text-center">
                Select a region on the PDF to extract data.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
