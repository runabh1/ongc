import React, { useState } from 'react';
import { checkDataExistence, findMissingValues, scanPdfMatches } from '../api';
import clsx from 'clsx';

interface Props {
  tableName: string;
  extractedData: any[];
  selectedFile: File | null;
}

interface ExistenceResult {
  exists: any[];
  missing: any[];
  found_count: number;
  missing_count: number;
}

interface MissingValuesResult {
  rows_with_missing: number;
  missing_details: Record<string, Record<string, string>>;
}

interface ScanResult {
  total_records_found: number;
  database_matches: number;
  no_matches: number;
  matches: any[];
  no_matches_data: any[];
}

export const DatabaseComparison: React.FC<Props> = ({ tableName, extractedData, selectedFile }) => {
  const [existenceResult, setExistenceResult] = useState<ExistenceResult | null>(null);
  const [missingResult, setMissingResult] = useState<MissingValuesResult | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCheckExistence = async () => {
    if (!extractedData.length) {
      setError('No data to check');
      return;
    }
    
    setLoading(true);
    setError('');
    try {
      const result = await checkDataExistence(extractedData, tableName);
      setExistenceResult(result);
    } catch (err: any) {
      setError(err.message || 'Error checking existence');
    } finally {
      setLoading(false);
    }
  };

  const handleFindMissing = async () => {
    if (!extractedData.length) {
      setError('No data to check');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await findMissingValues(extractedData, tableName);
      setMissingResult(result);
    } catch (err: any) {
      setError(err.message || 'Error finding missing values');
    } finally {
      setLoading(false);
    }
  };

  const handleScanPdfMatches = async () => {
    if (!selectedFile) {
      setError('No PDF file selected');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await scanPdfMatches(selectedFile, tableName);
      setScanResult(result);
    } catch (err: any) {
      setError(err.message || 'Error scanning PDF');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-8 space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-2xl font-bold mb-4">Database Comparison Tools</h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <button
            onClick={handleCheckExistence}
            disabled={loading || !extractedData.length}
            className={clsx(
              'px-4 py-2 rounded font-semibold text-white transition',
              loading || !extractedData.length
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            )}
          >
            {loading ? 'Checking...' : '🔍 Check Existence'}
          </button>

          <button
            onClick={handleFindMissing}
            disabled={loading || !extractedData.length}
            className={clsx(
              'px-4 py-2 rounded font-semibold text-white transition',
              loading || !extractedData.length
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-yellow-600 hover:bg-yellow-700'
            )}
          >
            {loading ? 'Checking...' : '⚠️ Find Missing Values'}
          </button>

          <button
            onClick={handleScanPdfMatches}
            disabled={loading || !selectedFile}
            className={clsx(
              'px-4 py-2 rounded font-semibold text-white transition',
              loading || !selectedFile
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700'
            )}
          >
            {loading ? 'Scanning...' : '📄 Scan PDF Matches'}
          </button>
        </div>

        {/* Existence Check Results */}
        {existenceResult && (
          <div className="mb-6 p-4 border-l-4 border-blue-500 bg-blue-50">
            <h3 className="font-bold text-lg mb-2">✓ Existence Check Results</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Found in Database</p>
                <p className="text-2xl font-bold text-blue-600">{existenceResult.found_count}</p>
              </div>
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Missing from Database</p>
                <p className="text-2xl font-bold text-red-600">{existenceResult.missing_count}</p>
              </div>
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Total Checked</p>
                <p className="text-2xl font-bold">{existenceResult.found_count + existenceResult.missing_count}</p>
              </div>
            </div>

            {existenceResult.exists.length > 0 && (
              <div className="mb-4">
                <p className="font-semibold text-green-700 mb-2">Records Found in Database:</p>
                <div className="max-h-64 overflow-y-auto bg-white p-3 rounded border border-green-200">
                  {existenceResult.exists.map((item: any, idx: number) => (
                    <div key={idx} className="mb-3 p-2 border-b border-green-100">
                      <p className="font-semibold text-sm">Match #{idx + 1}</p>
                      <p className="text-xs text-gray-600">{JSON.stringify(item.pdf_data).substring(0, 100)}...</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {existenceResult.missing.length > 0 && (
              <div>
                <p className="font-semibold text-red-700 mb-2">Records NOT in Database:</p>
                <div className="max-h-64 overflow-y-auto bg-white p-3 rounded border border-red-200">
                  {existenceResult.missing.map((item: any, idx: number) => (
                    <div key={idx} className="mb-2 p-2 border-b border-red-100">
                      <p className="text-xs text-gray-600">{JSON.stringify(item).substring(0, 100)}...</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Missing Values Results */}
        {missingResult && (
          <div className="mb-6 p-4 border-l-4 border-yellow-500 bg-yellow-50">
            <h3 className="font-bold text-lg mb-2">⚠️ Missing Values Report</h3>
            <div className="mb-4">
              <p className="text-gray-700">
                <span className="font-semibold">{missingResult.rows_with_missing}</span> rows have missing values
              </p>
            </div>

            {Object.keys(missingResult.missing_details).length > 0 && (
              <div className="max-h-80 overflow-y-auto bg-white p-3 rounded border border-yellow-200">
                {Object.entries(missingResult.missing_details).map(([rowKey, missing]: [string, any]) => (
                  <div key={rowKey} className="mb-3 p-2 border-b border-yellow-100">
                    <p className="font-semibold text-sm text-yellow-800">{rowKey}</p>
                    <div className="ml-4 text-xs text-gray-700">
                      {Object.keys(missing).map((field: string) => (
                        <p key={field} className="text-red-600">• {field}: MISSING</p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* PDF Scan Results */}
        {scanResult && (
          <div className="mb-6 p-4 border-l-4 border-green-500 bg-green-50">
            <h3 className="font-bold text-lg mb-2">📄 PDF Scan Results</h3>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Total Records in PDF</p>
                <p className="text-2xl font-bold text-blue-600">{scanResult.total_records_found}</p>
              </div>
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Database Matches</p>
                <p className="text-2xl font-bold text-green-600">{scanResult.database_matches}</p>
              </div>
              <div className="bg-white p-3 rounded">
                <p className="text-gray-600 text-sm">Not in Database</p>
                <p className="text-2xl font-bold text-red-600">{scanResult.no_matches}</p>
              </div>
            </div>

            {scanResult.matches.length > 0 && (
              <div className="mb-4">
                <p className="font-semibold text-green-700 mb-2">Matches Found:</p>
                <div className="max-h-48 overflow-y-auto bg-white p-3 rounded border border-green-200">
                  {scanResult.matches.map((match: any, idx: number) => (
                    <div key={idx} className="mb-2 p-2 border-b border-green-100">
                      <p className="text-xs">
                        <span className="font-semibold">Page {match.page}:</span> {match.status}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {scanResult.no_matches_data.length > 0 && (
              <div>
                <p className="font-semibold text-red-700 mb-2">Records NOT in Database:</p>
                <div className="max-h-48 overflow-y-auto bg-white p-3 rounded border border-red-200">
                  {scanResult.no_matches_data.map((item: any, idx: number) => (
                    <div key={idx} className="mb-2 p-2 border-b border-red-100">
                      <p className="text-xs">
                        <span className="font-semibold">Page {item.page}:</span> {item.status}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DatabaseComparison;
