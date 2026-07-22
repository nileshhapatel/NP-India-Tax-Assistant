import { useState } from 'react';
import { File, FileText, Loader2, AlertCircle, Link2, Eye, Pencil, Unlink, Trash2, Star, AlertTriangle, Download } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Documents() {
  const { selectedCaseId, selectedTaxpayerId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const taxpayerId = selectedTaxpayerId || 1;
  const { data: caseDocsData, error, isLoading, mutate: mutateCaseDocs } = useSWR(
    apiUrl(`/api/documents/case/${caseId}`),
    fetcher
  );
  const { data: vaultData, mutate: mutateVault } = useSWR(
    apiUrl(`/api/taxpayers/${taxpayerId}/documents/vault`),
    fetcher
  );
  const [busyCode, setBusyCode] = useState('');
  const [message, setMessage] = useState('');

  const caseDocs = caseDocsData?.documents || [];
  const uploadedInCase = caseDocs.filter((d) => !!d.file_path);
  const vaultDocs = vaultData?.documents || [];
  const reusableAvailable = vaultDocs.filter((d) => d.reusable_across_years).length;

  const refresh = async () => Promise.all([mutateCaseDocs(), mutateVault()]);

  const linkReusable = async (doc) => {
    setBusyCode(doc.code);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/documents/${doc.code}/link`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_document_id: doc.id }),
      });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || 'Link failed');
      setMessage(`Linked ${doc.code} to current case.`);
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const renameCurrent = async (doc, evidence) => {
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
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const unlinkCurrent = async (doc, evidence) => {
    if (!window.confirm(`Unlink ${doc.code} from this case?`)) return;
    setBusyCode(doc.code);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/documents/${doc.code}/unlink`, {
        delete_file: false,
        evidence_id: evidence?.id || null,
      });
      setMessage(`Unlinked ${doc.code}.`);
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const setPrimaryCurrent = async (doc, evidence) => {
    setBusyCode(doc.code);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/documents/${doc.code}/evidence/${evidence.id}/primary`);
      setMessage(`Primary source changed for ${doc.code}.`);
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  const deleteCurrent = async (doc) => {
    if (!window.confirm(`Delete ${doc.code}? Required documents are cleared, optional are removed.`)) return;
    setBusyCode(doc.code);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/documents/${doc.code}?delete_file=true`), { method: 'DELETE' });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || 'Delete failed');
      setMessage(`Deleted/cleared ${doc.code}.`);
      await refresh();
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
      await refresh();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setBusyCode('');
    }
  };

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  }
  if (error) {
    return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading documents</span></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <FileText className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Documents Vault</h1>
          <p className="text-gray-600">Current case can keep multiple files under one category, with a single primary source for amounts.</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Current case uploads</p><p className="text-2xl font-bold text-primary-600">{uploadedInCase.length}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Vault documents</p><p className="text-2xl font-bold text-blue-600">{vaultDocs.length}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Reusable across years</p><p className="text-2xl font-bold text-green-600">{reusableAvailable}</p></div>
      </div>
      <a href="/document-fetcher" className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2 hover:bg-primary-700">
        Go to Document Workflow (fetch/upload)
      </a>
      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.startsWith('Error:') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {message}
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Uploaded in Current Case</h2>
        <div className="space-y-3">
          {uploadedInCase.length === 0 ? (
            <p className="text-sm text-gray-600">No files linked to current case yet.</p>
          ) : (
            uploadedInCase.map((doc) => (
              <div key={doc.id || doc.code} className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <File className="w-4 h-4 text-gray-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{doc.display_title || doc.title}</p>
                      <p className="text-xs text-gray-500">{doc.code}</p>
                    </div>
                  </div>
                  <button onClick={() => deleteCurrent(doc)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-red-300 bg-red-50 text-red-700 hover:bg-red-100 disabled:bg-gray-100">
                    <Trash2 className="w-3 h-3" /> Delete category
                  </button>
                </div>
                <label className="inline-flex items-center gap-2 text-xs text-gray-700">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={doc.status === 'Not applicable'}
                    disabled={busyCode === doc.code}
                    onChange={(e) => toggleApplicability(doc, e.target.checked)}
                  />
                  Not applicable for this FY
                </label>
                {doc.has_multiple_sources && (
                  <div className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Multiple sources linked. Use Primary source for amount entry.
                  </div>
                )}
                <div className="space-y-2">
                  {(doc.evidences || []).map((evidence) => (
                    <div key={evidence.id} className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 border border-gray-200 bg-white rounded p-2">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{evidence.title}</p>
                        <p className="text-xs text-gray-500 break-all">{evidence.file_path}</p>
                        <span className={`inline-flex mt-1 text-[11px] px-2 py-0.5 rounded ${evidence.is_primary ? 'bg-primary-100 text-primary-700 border border-primary-200' : 'bg-gray-100 text-gray-600 border border-gray-200'}`}>
                          {evidence.is_primary ? 'Primary source' : 'Supporting source'}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <a href={apiUrl(`/api/document-evidences/${evidence.id}/preview`)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
                          <Eye className="w-3 h-3" /> Preview
                        </a>
                        <a href={apiUrl(`/api/document-evidences/${evidence.id}/preview?download=true`)} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
                          <Download className="w-3 h-3" /> Download
                        </a>
                        {!evidence.is_primary && (
                          <button onClick={() => setPrimaryCurrent(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-primary-300 bg-primary-50 text-primary-700 hover:bg-primary-100 disabled:bg-gray-100">
                            <Star className="w-3 h-3" /> Make primary
                          </button>
                        )}
                        <button onClick={() => renameCurrent(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:bg-gray-100">
                          <Pencil className="w-3 h-3" /> Rename file label
                        </button>
                        <button onClick={() => unlinkCurrent(doc, evidence)} disabled={busyCode === doc.code} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:bg-gray-100">
                          <Unlink className="w-3 h-3" /> Unlink
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {doc.status === 'Not applicable' && (
                  <p className="text-xs text-amber-700">
                    Marked not applicable{doc.not_applicable_reason ? `: ${doc.not_applicable_reason}` : '.'}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">All Uploaded Documents (Taxpayer Vault)</h2>
        <div className="space-y-2">
          {vaultDocs.length === 0 ? (
            <p className="text-sm text-gray-600">No uploaded files found for this taxpayer.</p>
          ) : (
            vaultDocs.map((doc) => (
              <div key={doc.id} className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div>
                  <p className="text-sm font-semibold text-gray-900">{doc.title}</p>
                  <p className="text-xs text-gray-500">
                    {doc.code} • FY {doc.financial_year} • AY {doc.assessment_year} • case {doc.case_id}
                  </p>
                  <p className="text-xs text-gray-500 break-all">{doc.file_path}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <a href={apiUrl(`/api/documents/${doc.id}/preview`)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
                    <Eye className="w-3 h-3" /> Preview
                  </a>
                  <a href={apiUrl(`/api/documents/${doc.id}/preview?download=true`)} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
                    <Download className="w-3 h-3" /> Download
                  </a>
                  {doc.reusable_across_years && (
                    <button
                      onClick={() => linkReusable(doc)}
                      disabled={busyCode === doc.code}
                      className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:bg-gray-100"
                    >
                      <Link2 className="w-4 h-4" />
                      Link to current case
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
