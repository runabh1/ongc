import React from 'react';

interface Props {
  data: any[];
  rawData: any[];
  schema: string[];
  onExport: () => void;
  onSave: () => void;
  onExportPdf: () => void;
  onCheckExistence: () => void;
}

export const ResultsTable: React.FC<Props> = ({ data, rawData, schema, onExport, onSave, onExportPdf, onCheckExistence }) => {
  if ((!data || data.length === 0) && (!rawData || rawData.length === 0)) {
    return (
      <div className="p-4 bg-yellow-50 border border-yellow-200 rounded text-yellow-800 text-center">
        No text or data could be extracted from this region.
      </div>
    );
  }

  // Calculate missing values summary
  const missingSummary = data.reduce((acc: string[], row) => {
    const errors = row._errors || "";
    if (errors.includes("Missing:")) {
      const missingCols = errors.split("; ").filter((e: string) => e.startsWith("Missing:"));
      return [...acc, ...missingCols];
    }
    return acc;
  }, []);
  const uniqueMissing = Array.from(new Set(missingSummary));

  // Get headers for raw data
  const rawHeaders = rawData.length > 0 ? Object.keys(rawData[0]).filter(k => !k.startsWith('_')) : [];

  return (
    <div className="mt-4 space-y-8 pb-10">
      
      {/* 1. Raw Extracted Data */}
      {rawData.length > 0 && (
        <div className="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
            <h3 className="font-bold text-gray-800 flex items-center gap-2">
              <span className="bg-gray-200 text-gray-600 text-xs px-2 py-1 rounded">RAW</span>
              Extracted Data
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {rawHeaders.map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {rawData.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    {rawHeaders.map(h => (
                      <td key={h} className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                        {row[h]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 2. SQL Mapped Data */}
      {data && data.length > 0 && (
        <div className="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center flex-wrap gap-4">
          <h3 className="font-bold text-gray-800 flex items-center gap-2">
            <span className="bg-blue-100 text-blue-700 text-xs px-2 py-1 rounded">DATA</span>
            Mapped Data
          </h3>
          <div className="flex gap-3">
            <button onClick={onCheckExistence} className="inline-flex items-center px-3 py-1.5 border border-blue-200 text-sm font-medium rounded-md text-blue-700 bg-blue-50 hover:bg-blue-100 shadow-sm transition-colors">
              🔍 Check Existence
            </button>
            <button onClick={onSave} className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 shadow-sm transition-colors">
              Add to Database
            </button>
            <button onClick={onExport} className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 shadow-sm transition-colors">
              Export CSV
            </button>
            <button onClick={onExportPdf} className="inline-flex items-center px-3 py-1.5 border border-red-200 text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 shadow-sm transition-colors">
              Export PDF
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">DB Status</th>
                {schema.map(col => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.map((row, idx) => (
                <tr key={idx} className={row._status === 'INVALID' ? 'bg-red-50' : 'bg-green-50'}>
                  <td className="px-4 py-3 whitespace-nowrap text-center">
                    {row._status === 'VALID' ? '✅' : '❌'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-center">
                    {row._db_status === 'EXISTING' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                        IN DB
                      </span>
                    ) : row._db_status === 'NEW' ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                        NEW
                      </span>
                    ) : '-'}
                  </td>
                  {schema.map(col => {
                    return (
                      <td key={col} className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                        {row[col] !== undefined && row[col] !== null && row[col] !== "" ? (
                          row[col]
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                            MISSING
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
      )}

      {/* 3. Missing Values Summary */}
      {uniqueMissing.length > 0 && data.length > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded shadow">
          <h3 className="font-bold text-lg mb-2 text-red-700">3. Missing Values Summary</h3>
          <ul className="list-disc list-inside text-red-800">
            {uniqueMissing.map((msg, i) => (
              <li key={i}>{String(msg).replace("Missing: ", "")} column is missing in one or more rows.</li>
            ))}
          </ul>
        </div>
      )}
      
      {uniqueMissing.length === 0 && data && data.length > 0 && (
        <div className="p-4 bg-green-50 border border-green-200 rounded shadow text-green-800">
          <h3 className="font-bold text-lg">3. Data Completeness</h3>
          <p>All expected SQL columns are present!</p>
        </div>
      )}

      </div>
  );
};