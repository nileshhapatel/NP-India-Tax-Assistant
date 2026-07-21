import { useState } from 'react';
import { ExternalLink, FileUp, Link2, CheckCircle2, Loader2 } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function DocumentFetcher() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, mutate, isLoading } = useSWR(apiUrl(`/api/cases/${caseId}/documents/required`), fetcher);
  const [busyCode, setBusyCode] = useState('');
  const [message, setMessage] = useState('');
  const docs = data?.documents || [];

  const uploadForCode = async (code, file) => {
    if (!file) return;
    setBusyCode(code);
    setMessage('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('case_id', String(caseId));
      formData.append('code', code);
      formData.append('document_type', code);
      const res = await fetch(apiUrl('/api/documents/upload'), { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Upload failed (${res.status})`);
      setMessage(`Uploaded ${code} successfully.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const reuseFromPriorYear = async (code) => {
    setBusyCode(code);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/documents/${code}/reuse`), { method: 'POST' });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || `Reuse failed (${res.status})`);
      setMessage(`Linked ${code} from previous tax year.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const statusClass = (status) =>
    status === 'Verified'
      ? 'bg-green-100 text-green-700'
      : status === 'Received'
      ? 'bg-blue-100 text-blue-700'
      : 'bg-gray-100 text-gray-600';

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <FileUp className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Document Workflow</h1>
          <p className="text-gray-600">Fetch from portal and upload/link directly for Case {caseId}. Documents page now acts as uploaded vault.</p>
        </div>
      </div>
      <div className="flex gap-2">
        <a href="/documents" className="inline-flex items-center gap-2 rounded-lg bg-gray-100 border border-gray-300 px-3 py-2 text-sm text-gray-800 hover:bg-gray-200">
          <CheckCircle2 className="w-4 h-4" />
          Open Documents Vault
        </a>
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.startsWith('Error:') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {message}
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
          <h2 className="text-lg font-semibold text-gray-900">Required Documents (Portal + Upload + Reuse)</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {docs.map((doc) => (
            <div key={doc.id || doc.code} className="p-4 md:p-6 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold text-gray-900">{doc.title}</p>
                  <p className="text-xs text-gray-500">{doc.code} • {doc.category} • {doc.required ? 'Required' : 'Optional'}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded ${statusClass(doc.status)}`}>{doc.status || 'Missing'}</span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {doc.portal?.url ? (
                  <a
                    href={doc.portal.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-primary-200 text-primary-700 bg-primary-50 hover:bg-primary-100"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Open {doc.portal.name || 'Portal'}
                  </a>
                ) : (
                  <span className="text-xs text-gray-500">Portal link not configured. Use institution source: {doc.institution || 'Manual source'}.</span>
                )}

                <label className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
                  <FileUp className="w-4 h-4" />
                  Upload for this doc
                  <input
                    type="file"
                    className="hidden"
                    onChange={(e) => uploadForCode(doc.code, e.target.files?.[0])}
                  />
                </label>

                {doc.reusable_across_years && !doc.file_path && doc.link_candidate && (
                  <button
                    onClick={() => reuseFromPriorYear(doc.code)}
                    disabled={busyCode === doc.code}
                    className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:bg-gray-100"
                  >
                    <Link2 className="w-4 h-4" />
                    {busyCode === doc.code ? 'Linking...' : `Reuse from case ${doc.link_candidate.source_case_id}`}
                  </button>
                )}

                {doc.file_path && (
                  <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1">
                    <CheckCircle2 className="w-3 h-3" />
                    Uploaded / linked
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
