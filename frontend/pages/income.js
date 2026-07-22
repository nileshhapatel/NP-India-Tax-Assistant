import { useMemo, useState } from 'react';
import { Plus, Trash2, Loader2, AlertCircle, AlertTriangle, DollarSign, Info, Sparkles, Download } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const INCOME_TYPES = [
  { label: 'Salary (India-source)', value: 'salary_india' },
  { label: 'Salary (Foreign-source)', value: 'salary_foreign' },
  { label: 'Interest (Savings)', value: 'interest_savings' },
  { label: 'Interest (Other)', value: 'interest_other' },
  { label: 'Dividend Income', value: 'dividend' },
  { label: 'Capital Gains (Short-term)', value: 'cg_short' },
  { label: 'Capital Gains (Long-term)', value: 'cg_long' },
  { label: 'Rental Income', value: 'rental' },
  { label: 'Freelance/Professional', value: 'professional' },
  { label: 'Other Income', value: 'other' },
];

const fmt = (value) => `₹${Number(value || 0).toLocaleString()}`;

export default function Income() {
  const { selectedCaseId, selectedCase } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: incomeData, isLoading, error, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/income`), fetcher);

  const [newEntry, setNewEntry] = useState({
    income_type: 'salary_india',
    source_name: '',
    amount: '',
    tds_deducted: '',
    amount_in_return: '',
    evidence_code: '',
    notes: '',
    fiscal_year: '2025-26',
  });
  const [message, setMessage] = useState('');
  const [adding, setAdding] = useState(false);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [applyingDraft, setApplyingDraft] = useState(false);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [draft, setDraft] = useState(null);
  const [selectedDraftIndexes, setSelectedDraftIndexes] = useState([]);

  const entries = incomeData?.income_entries || [];
  const totalIncome = entries.reduce((sum, e) => sum + (parseFloat(e.gross_amount) || 0), 0);
  const totalTds = entries.reduce((sum, e) => sum + (parseFloat(e.tds_amount) || 0), 0);
  const totalInReturn = entries.reduce((sum, e) => sum + (parseFloat(e.amount_in_return) || 0), 0);

  const typeBreakdown = useMemo(() => {
    const result = {};
    for (const e of entries) {
      const key = e.income_type || 'other';
      result[key] = (result[key] || 0) + (parseFloat(e.gross_amount) || 0);
    }
    return Object.entries(result).sort((a, b) => b[1] - a[1]);
  }, [entries]);

  const handleAddIncome = async () => {
    if (!newEntry.amount || parseFloat(newEntry.amount) <= 0) {
      setMessage('Please enter a valid income amount.');
      return;
    }
    setAdding(true);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/income`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          income_type: newEntry.income_type,
          source_name: newEntry.source_name || newEntry.income_type,
          amount: parseFloat(newEntry.amount),
          tds_deducted: parseFloat(newEntry.tds_deducted) || 0,
          amount_in_return: newEntry.amount_in_return ? parseFloat(newEntry.amount_in_return) : parseFloat(newEntry.amount),
          evidence_code: newEntry.evidence_code || null,
          notes: newEntry.notes || null,
          fiscal_year: newEntry.fiscal_year,
        }),
      });
      const result = await res.json();
      if (!res.ok || !result.ok) throw new Error(result.error || `Failed (${res.status})`);
      setMessage('Income entry added.');
      setNewEntry((prev) => ({ ...prev, amount: '', tds_deducted: '', amount_in_return: '', notes: '' }));
      await mutate();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (incomeId) => {
    if (!window.confirm('Delete this income entry?')) return;
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/income/${incomeId}`), { method: 'DELETE' });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.error || `Failed (${res.status})`);
      setMessage('Entry deleted.');
      await mutate();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
  };

  const generateAutoDraft = async () => {
    setGeneratingDraft(true);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/income/auto-draft`), { method: 'POST' });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || `Failed (${res.status})`);
      const rows = (payload.draft_entries || []).map((row) => ({ ...row }));
      setDraft({ ...payload, draft_entries: rows });
      // Auto-select only non-duplicate entries
      setSelectedDraftIndexes(rows.reduce((acc, row, idx) => {
        if (!row.is_duplicate) acc.push(idx);
        return acc;
      }, []));
      const dupCount = payload.totals?.duplicate_count || 0;
      setMessage(`Generated ${rows.length} draft entries from uploaded documents${dupCount > 0 ? ` — ${dupCount} duplicate(s) auto-excluded` : ''}.`);
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setGeneratingDraft(false);
    }
  };

  const toggleDraftSelection = (index) => {
    setSelectedDraftIndexes((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const updateDraftRow = (index, field, value) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const rows = [...(prev.draft_entries || [])];
      rows[index] = { ...rows[index], [field]: value };
      return { ...prev, draft_entries: rows };
    });
  };

  const applySelectedDraft = async () => {
    if (!draft?.draft_entries?.length) return;
    const selected = selectedDraftIndexes
      .sort((a, b) => a - b)
      .map((idx) => draft.draft_entries[idx])
      .filter(Boolean);
    if (!selected.length) {
      setMessage('Select at least one draft entry to apply.');
      return;
    }
    setApplyingDraft(true);
    setMessage('');
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/income/auto-apply`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          replace_existing: replaceExisting,
          entries: selected.map((row) => ({
            income_type: row.income_type,
            source_name: row.source_name,
            gross_amount: parseFloat(row.gross_amount || 0),
            tds_amount: parseFloat(row.tds_amount || 0),
            doc_code: row.doc_code || null,
            evidence_id: row.evidence_id || null,
            rationale: row.rationale || null,
            confidence: row.confidence || null,
          })),
        }),
      });
      const payload = await res.json();
      if (!res.ok || !payload.ok) throw new Error(payload.detail || payload.error || `Failed (${res.status})`);
      setMessage(`Applied auto-draft entries. Created: ${payload.created}, Skipped duplicates/zero: ${payload.skipped}.`);
      await mutate();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setApplyingDraft(false);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (error) return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading income data</span></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <DollarSign className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Income Register (Advanced)</h1>
          <p className="text-gray-600">Case {caseId} • FY {selectedCase?.financial_year || '—'} • Auto-draft from uploaded documents, then review and apply.</p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900 flex items-start gap-2">
        <Info className="w-4 h-4 mt-0.5" />
        Auto-draft reads uploaded proofs and prepares draft entries. You control what gets applied; nothing is posted without review.
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-200"><p className="text-sm text-gray-600">Total Income</p><p className="text-2xl font-bold text-blue-600">{fmt(totalIncome)}</p></div>
        <div className="p-4 bg-green-50 rounded-lg border border-green-200"><p className="text-sm text-gray-600">Total TDS</p><p className="text-2xl font-bold text-green-600">{fmt(totalTds)}</p></div>
        <div className="p-4 bg-purple-50 rounded-lg border border-purple-200"><p className="text-sm text-gray-600">Amount in Return</p><p className="text-2xl font-bold text-purple-600">{fmt(totalInReturn)}</p></div>
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200"><p className="text-sm text-gray-600">Entries</p><p className="text-2xl font-bold text-gray-700">{entries.length}</p></div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-gray-900">Auto-Draft from Uploaded Documents</h2>
          <button onClick={generateAutoDraft} disabled={generatingDraft} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:bg-gray-400">
            <Sparkles className="w-4 h-4" />
            {generatingDraft ? 'Generating...' : 'Generate auto-draft'}
          </button>
        </div>

        {draft && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <div className="rounded border border-gray-200 bg-gray-50 p-3"><p className="text-gray-600">Docs scanned</p><p className="font-bold">{draft.totals?.documents_scanned || 0}</p></div>
              <div className="rounded border border-gray-200 bg-gray-50 p-3"><p className="text-gray-600">Total drafts</p><p className="font-bold">{draft.totals?.total_draft || 0}</p></div>
              <div className="rounded border border-amber-300 bg-amber-50 p-3"><p className="text-amber-700">Duplicates</p><p className="font-bold text-amber-800">{draft.totals?.duplicate_count || 0}</p></div>
              <div className="rounded border border-green-200 bg-green-50 p-3"><p className="text-green-700">Selected gross</p><p className="font-bold text-green-800">{fmt(draft.totals?.gross_amount || 0)}</p></div>
              <div className="rounded border border-green-200 bg-green-50 p-3"><p className="text-green-700">Selected TDS</p><p className="font-bold text-green-800">{fmt(draft.totals?.tds_amount || 0)}</p></div>
            </div>

            {(draft.totals?.duplicate_count || 0) > 0 && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>
                  <strong>{draft.totals.duplicate_count} duplicate {draft.totals.duplicate_count === 1 ? 'entry' : 'entries'} detected</strong> — the same income appears in multiple documents (e.g., both an interest certificate and Form 26AS).
                  Duplicates are <strong>auto-unchecked</strong> to prevent double-counting. The preferred source (specific certificate) is kept. You can manually re-check a duplicate if you need it instead.
                </span>
              </div>
            )}

            {(draft.draft_entries || []).length === 0 ? (
              <p className="text-sm text-gray-600">No draft entries extracted from current uploaded documents.</p>
            ) : (
              <div className="space-y-2">
                {draft.draft_entries.map((row, index) => (
                  <div key={`${row.doc_code || 'doc'}-${index}`}
                    className={`rounded border p-3 ${row.is_duplicate
                      ? 'border-amber-200 bg-amber-50 opacity-75'
                      : 'border-gray-200 bg-gray-50'}`}>
                    <div className="flex items-start justify-between gap-3">
                      <label className="inline-flex items-start gap-2 text-sm">
                        <input type="checkbox" checked={selectedDraftIndexes.includes(index)} onChange={() => toggleDraftSelection(index)} className="mt-0.5 h-4 w-4" />
                        <span>
                          <span className={`font-medium ${row.is_duplicate ? 'text-amber-800' : 'text-gray-900'}`}>
                            {row.source_name}
                            {row.is_duplicate && (
                              <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-800">
                                <AlertTriangle className="w-3 h-3" /> Duplicate
                              </span>
                            )}
                            {row.duplicate_group && !row.is_duplicate && (
                              <span className="ml-2 inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">
                                ✓ Preferred source
                              </span>
                            )}
                          </span>
                          <span className="block text-xs text-gray-500">{row.doc_code || 'No code'} • Confidence: {row.confidence || 'low'}</span>
                          {row.is_duplicate && row.duplicate_of && (
                            <span className="block text-xs text-amber-700 mt-0.5">
                              Same income already covered by: <strong>{row.duplicate_of}</strong>
                            </span>
                          )}
                          {row.rationale && <span className="block text-xs text-gray-600 mt-1">{row.rationale}</span>}
                        </span>
                      </label>
                      {row.evidence_id && (
                        <a href={apiUrl(`/api/document-evidences/${row.evidence_id}/preview?download=true`)} className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 shrink-0">
                          <Download className="w-3 h-3" /> Source
                        </a>
                      )}
                    </div>
                    {!row.is_duplicate && (
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2">
                      <select value={row.income_type} onChange={(e) => updateDraftRow(index, 'income_type', e.target.value)} className="px-2 py-1.5 border border-gray-300 rounded text-sm bg-white">
                        {INCOME_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                      </select>
                      <input type="number" value={row.gross_amount} onChange={(e) => updateDraftRow(index, 'gross_amount', e.target.value)} className="px-2 py-1.5 border border-gray-300 rounded text-sm" placeholder="Gross amount" />
                      <input type="number" value={row.tds_amount} onChange={(e) => updateDraftRow(index, 'tds_amount', e.target.value)} className="px-2 py-1.5 border border-gray-300 rounded text-sm" placeholder="TDS amount" />
                      <input type="text" value={row.source_name} onChange={(e) => updateDraftRow(index, 'source_name', e.target.value)} className="px-2 py-1.5 border border-gray-300 rounded text-sm" placeholder="Source label" />
                    </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)} className="h-4 w-4" />
                Replace existing income entries when applying
              </label>
              <button onClick={applySelectedDraft} disabled={applyingDraft || selectedDraftIndexes.length === 0} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:bg-gray-400">
                {applyingDraft ? 'Applying...' : `Apply ${selectedDraftIndexes.length} of ${(draft.draft_entries || []).length} entries`}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Add / Override Entry Manually</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Income Type</span>
            <select value={newEntry.income_type} onChange={(e) => setNewEntry({ ...newEntry, income_type: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg">
              {INCOME_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Source Name</span>
            <input type="text" value={newEntry.source_name} onChange={(e) => setNewEntry({ ...newEntry, source_name: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" placeholder="e.g., BOB NRO Interest Certificate" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Evidence Code</span>
            <input type="text" value={newEntry.evidence_code} onChange={(e) => setNewEntry({ ...newEntry, evidence_code: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" placeholder="e.g., BOB_NRO_INT" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Gross Amount (₹)</span>
            <input type="number" value={newEntry.amount} onChange={(e) => setNewEntry({ ...newEntry, amount: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">TDS (₹)</span>
            <input type="number" value={newEntry.tds_deducted} onChange={(e) => setNewEntry({ ...newEntry, tds_deducted: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Amount in Return (₹)</span>
            <input type="number" value={newEntry.amount_in_return} onChange={(e) => setNewEntry({ ...newEntry, amount_in_return: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
        </div>
        <label className="block mt-4">
          <span className="block text-sm font-medium text-gray-700">Notes</span>
          <textarea value={newEntry.notes} onChange={(e) => setNewEntry({ ...newEntry, notes: e.target.value })} rows={2} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" placeholder="Any context, adjustments, or mapping notes" />
        </label>
        <button onClick={handleAddIncome} disabled={adding} className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400">
          <Plus className="w-4 h-4" />
          {adding ? 'Adding...' : 'Add Entry'}
        </button>
      </div>

      {typeBreakdown.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Income Mix by Type</h2>
          <div className="flex flex-wrap gap-2">
            {typeBreakdown.map(([type, amount]) => (
              <span key={type} className="inline-flex items-center rounded-full border border-gray-300 bg-gray-50 px-3 py-1 text-sm text-gray-700">
                {type}: {fmt(amount)}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Income Entries</h2>
        <div className="space-y-2">
          {entries.length === 0 ? (
            <p className="text-gray-600 text-sm">No income entries yet.</p>
          ) : (
            entries.map((entry) => (
              <div key={entry.id} className="flex justify-between items-start p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-semibold text-gray-900">{entry.source_name || entry.income_type}</p>
                  <p className="text-xs text-gray-500">{entry.income_type}{entry.evidence_code ? ` • ${entry.evidence_code}` : ''}</p>
                  <p className="text-sm text-gray-600">Gross: {fmt(entry.gross_amount)} | Return: {fmt(entry.amount_in_return)} | TDS: {fmt(entry.tds_amount)}</p>
                  {entry.notes && <p className="text-xs text-gray-500 mt-1">{entry.notes}</p>}
                </div>
                <button onClick={() => handleDelete(entry.id)} className="text-red-600 hover:text-red-700">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {message && <div className={`p-3 rounded-lg text-sm ${message.startsWith('Error:') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{message}</div>}
    </div>
  );
}
