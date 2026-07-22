import { useState } from 'react';
import { ExternalLink, FileUp, Link2, CheckCircle2, Loader2, Pencil, Unlink, Trash2, Eye, Star, AlertTriangle, Download } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
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
      setMessage(`Uploaded ${code}. Latest upload is set as primary source.`);
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
      setMessage(`Linked ${code} from previous tax year as an additional source.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const renameDocument = async (doc, evidence) => {
    const currentTitle = evidence?.title || doc.title || '';
    const nextTitle = window.prompt('Rename document title', currentTitle);
    if (!nextTitle || nextTitle.trim() === currentTitle) return;
    setBusyCode(doc.code);
    setMessage('');
    try {
      await apiCall('PUT', `/api/cases/${caseId}/documents/${doc.code}/rename`, {
        title: nextTitle.trim(),
        evidence_id: evidence?.id || null,
      });
      setMessage(`Renamed ${doc.code}.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const unlinkDocument = async (doc, evidence) => {
    if (!window.confirm(`Unlink file from ${doc.code}?`)) return;
    setBusyCode(doc.code);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/documents/${doc.code}/unlink`, {
        delete_file: false,
        evidence_id: evidence?.id || null,
      });
      setMessage(`Unlinked ${doc.code}.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const setPrimaryEvidence = async (doc, evidence) => {
    setBusyCode(doc.code);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/documents/${doc.code}/evidence/${evidence.id}/primary`);
      setMessage(`Primary source set for ${doc.code}.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const deleteDocument = async (doc) => {
    if (!window.confirm(`Delete ${doc.code}? Required documents will be cleared, optional ones removed.`)) return;
    setBusyCode(doc.code);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/documents/${doc.code}?delete_file=true`), { method: 'DELETE' });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || `Delete failed (${res.status})`);
      setMessage(`Deleted/cleared ${doc.code}.`);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const toggleApplicability = async (doc, checkedNotApplicable) => {
    setBusyCode(doc.code);
    setMessage('');
    try {
      const reason = checkedNotApplicable
        ? (window.prompt(`Why is ${doc.code} not applicable for this FY? (optional)`) || '').trim()
        : '';
      await apiCall('POST', `/api/cases/${caseId}/documents/${doc.code}/applicability`, {
        applicable: !checkedNotApplicable,
        reason,
      });
      setMessage(
        checkedNotApplicable
          ? `${doc.code} marked as Not applicable.`
          : `${doc.code} marked as Applicable.`
      );
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
      : status === 'Not applicable'
      ? 'bg-amber-100 text-amber-700'
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
          <p className="text-gray-600">Fetch from portal and upload/link directly for Case {caseId}. One category can hold multiple source files.</p>
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
          {docs.map((doc) => {
            const evidences = doc.evidences || [];
            return (
              <div key={doc.id || doc.code} className="p-4 md:p-6 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-gray-900">{doc.display_title || doc.title}</p>
                    <p className="text-xs text-gray-500">{doc.code} • {doc.category} • {doc.required ? 'Required' : 'Optional'}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${statusClass(doc.status)}`}>{doc.status || 'Missing'}</span>
                </div>

                {doc.has_multiple_sources && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 flex items-center gap-2">
                    <AlertTriangle className="w-3 h-3" />
                    Multiple files linked. Enter amounts from only the Primary source to avoid double counting.
                  </div>
                )}

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
                  <label className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={doc.status === 'Not applicable'}
                      disabled={busyCode === doc.code}
                      onChange={(e) => toggleApplicability(doc, e.target.checked)}
                    />
                    Not applicable
                  </label>

                  {doc.reusable_across_years && doc.link_candidate && (
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
                  {doc.file_path && (
                    <button
                      onClick={() => deleteDocument(doc)}
                      disabled={busyCode === doc.code}
                      className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-red-300 text-red-700 bg-red-50 hover:bg-red-100 disabled:bg-gray-100"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete category links
                    </button>
                  )}
                </div>

                {evidences.length > 0 && (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
                    {evidences.map((evidence) => (
                      <div key={evidence.id} className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 rounded border border-gray-200 bg-white p-2">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{evidence.title || 'Untitled document'}</p>
                          <p className="text-xs text-gray-500 break-all">{evidence.file_path}</p>
                          <span className={`inline-flex mt-1 text-[11px] px-2 py-0.5 rounded ${evidence.is_primary ? 'bg-primary-100 text-primary-700 border border-primary-200' : 'bg-gray-100 text-gray-600 border border-gray-200'}`}>
                            {evidence.is_primary ? 'Primary source' : 'Supporting source'}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <a href={apiUrl(`/api/document-evidences/${evidence.id}/preview`)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"><Eye className="w-3 h-3" />Preview</a>
                          <a href={apiUrl(`/api/document-evidences/${evidence.id}/preview?download=true`)} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"><Download className="w-3 h-3" />Download</a>
                          {!evidence.is_primary && (
                            <button onClick={() => setPrimaryEvidence(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-primary-300 bg-primary-50 text-primary-700 hover:bg-primary-100 disabled:bg-gray-100">
                              <Star className="w-3 h-3" />
                              Make primary
                            </button>
                          )}
                          <button onClick={() => renameDocument(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:bg-gray-100"><Pencil className="w-3 h-3" />Rename file label</button>
                          <button onClick={() => unlinkDocument(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:bg-gray-100"><Unlink className="w-3 h-3" />Unlink</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {doc.status === 'Not applicable' && (
                  <p className="text-xs text-amber-700">
                    Marked not applicable{doc.not_applicable_reason ? `: ${doc.not_applicable_reason}` : '.'}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
