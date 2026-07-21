import { useState } from 'react';
import { Download, Loader2, AlertCircle, Check } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Export() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: caseData, error, isLoading } = useSWR(
    apiUrl(`/api/cases/${caseId}`),
    fetcher
  );
  const { data: checksData } = useSWR(apiUrl(`/api/cases/${caseId}/review-checks`), fetcher);

  const [exportFormat, setExportFormat] = useState('json');
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState('');
  const checks = checksData?.checks || [];
  const blockers = checks.filter((c) => c.severity === 'BLOCK');

  const handleExport = async () => {
    setExporting(true);
    setMessage('');

    try {
      const response = await fetch(
        apiUrl(`/api/portal/export?case_id=${caseId}&format=${exportFormat}`),
        {
          method: 'GET',
          headers: { Accept: 'application/json' },
        }
      );

      if (!response.ok) throw new Error(`Export failed: ${response.statusText}`);

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `itr-export.${exportFormat === 'json' ? 'json' : 'csv'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);

      setMessage(`✓ Exported successfully as ${exportFormat.toUpperCase()}`);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-600">
        <AlertCircle className="w-6 h-6" />
        <span>Error loading export data</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Download className="w-8 h-8 text-primary-600" />
        <h1 className="text-3xl font-bold text-gray-900">Export & File</h1>
      </div>

      {/* Export Options */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Export Format</h2>
        {blockers.length > 0 && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {blockers.length} blocker(s) still open. Resolve blockers in <a href="/review" className="underline font-semibold">Review</a> before final filing export.
          </div>
        )}
        <div className="space-y-3">
          {['json', 'csv', 'xml'].map((fmt) => (
            <label key={fmt} className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                value={fmt}
                checked={exportFormat === fmt}
                onChange={(e) => setExportFormat(e.target.value)}
                className="w-4 h-4"
              />
              <span className="font-medium text-gray-900">{fmt.toUpperCase()} Format</span>
              <span className="text-sm text-gray-600">
                {fmt === 'json' && 'Machine-readable ITR data'}
                {fmt === 'csv' && 'Spreadsheet-compatible format'}
                {fmt === 'xml' && 'Offline utility format'}
              </span>
            </label>
          ))}
        </div>

        <button
          onClick={handleExport}
          disabled={exporting}
          className="mt-6 w-full px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 font-semibold"
        >
          {exporting ? 'Exporting...' : 'Export'}
        </button>

        {message && (
          <div className="mt-4 p-3 rounded-lg bg-green-50 text-green-700 text-sm">
            {message}
          </div>
        )}
      </div>

      {/* Filing Information */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-blue-900 mb-3">About Filing</h2>
        <ul className="space-y-2 text-blue-900 text-sm">
          <li>• Export your ITR in your preferred format</li>
          <li>• JSON format is recommended for backup and portability</li>
          <li>• XML format is compatible with Income Tax Department offline utility</li>
          <li>• CSV format is for spreadsheet review</li>
          <li>• Final filing should be completed through the official portal or offline utility</li>
        </ul>
      </div>
    </div>
  );
}
