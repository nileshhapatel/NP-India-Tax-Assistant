import { History, Loader2, AlertCircle } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function HistoryPage() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, error, isLoading } = useSWR(apiUrl(`/api/cases/${caseId}/audit-history`), fetcher);

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (error) return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading audit history</span></div>;

  const rows = data?.history || [];
  const recent = rows.slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <History className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Audit History</h1>
          <p className="text-gray-600">Change log for the current case</p>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        {recent.length > 0 && (
          <div className="mb-4 grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg bg-blue-50 border border-blue-200 px-3 py-2">Total events: <strong>{rows.length}</strong></div>
            <div className="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2">Latest action: <strong>{recent[0]?.action || '—'}</strong></div>
          </div>
        )}
        {rows.length === 0 ? (
          <p className="text-sm text-gray-600">No audit events recorded yet.</p>
        ) : (
          <div className="space-y-3">
            {rows.map((row) => (
              <div key={row.id} className="rounded-lg bg-gray-50 border border-gray-200 p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <div>
                    <p className="font-semibold text-gray-900">{row.action}</p>
                    <p className="text-sm text-gray-600">{row.entity}</p>
                  </div>
                  <p className="text-xs text-gray-500">{row.event_time || '—'}</p>
                </div>
                {row.details && <p className="mt-2 text-sm text-gray-700">{row.details}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
