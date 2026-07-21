import { File, FileText, Loader2, AlertCircle, Link2 } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
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

  const caseDocs = caseDocsData?.documents || [];
  const uploadedInCase = caseDocs.filter((d) => !!d.file_path);
  const vaultDocs = vaultData?.documents || [];
  const reusableAvailable = vaultDocs.filter((d) => d.reusable_across_years).length;

  const linkReusable = async (code) => {
    const res = await fetch(apiUrl(`/api/cases/${caseId}/documents/${code}/reuse`), { method: 'POST' });
    const payload = await res.json();
    if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || 'Link failed');
    await Promise.all([mutateCaseDocs(), mutateVault()]);
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
          <p className="text-gray-600">Uploaded files across years. Use Document Workflow page to fetch + upload directly.</p>
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

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Uploaded in Current Case</h2>
        <div className="space-y-2">
          {uploadedInCase.length === 0 ? (
            <p className="text-sm text-gray-600">No files linked to current case yet.</p>
          ) : (
            uploadedInCase.map((doc) => (
              <div key={doc.id || doc.code} className="flex items-center justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center gap-2">
                  <File className="w-4 h-4 text-gray-600" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{doc.title}</p>
                    <p className="text-xs text-gray-500">{doc.code}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-500 break-all max-w-md text-right">{doc.file_path}</span>
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
                {doc.reusable_across_years && !uploadedInCase.find((c) => c.code === doc.code) && (
                  <button
                    onClick={() => linkReusable(doc.code)}
                    className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-lg border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100"
                  >
                    <Link2 className="w-4 h-4" />
                    Link to current case
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
