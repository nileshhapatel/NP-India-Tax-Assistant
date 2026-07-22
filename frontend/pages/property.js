import { useMemo, useState } from 'react';
import { Building2, Loader2, AlertCircle, Plus, Pencil, Landmark, Home, Hammer, Sparkles, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const DEFAULT_FORM = {
  property_name: '',
  property_address: '',
  ownership_percent: '',
  self_occupied: true,
  possession_date: '',
  loan_start_date: '',
  lender: '',
  interest_fy: '',
  principal_fy: '',
  preconstruction_interest: '',
  actual_payment_percent: '',
  notes: '',
};

const inr = (v) => `₹${Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
const fmt2 = (v) => `₹${Number(v || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function PropertyTag({ item }) {
  const underConstruction = !item.possession_date;
  if (underConstruction) return <span className="text-xs px-2 py-1 rounded bg-orange-100 text-orange-700">🏗️ Under construction</span>;
  if (item.self_occupied) return <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">🏠 Self-occupied</span>;
  return <span className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700">🏢 Let-out / deemed let-out</span>;
}

export default function Property() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, error, isLoading, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/properties`), fetcher);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [message, setMessage] = useState('');
  const [loanParsed, setLoanParsed] = useState(null);
  const [parsingLoan, setParsingLoan] = useState(false);
  const [showLoanPanel, setShowLoanPanel] = useState(false);

  const properties = data?.properties || [];
  const totals = useMemo(() => {
    return properties.reduce(
      (acc, item) => {
        acc.interest += Number(item.interest_fy || 0);
        acc.principal += Number(item.principal_fy || 0);
        acc.preconstruction += Number(item.preconstruction_interest || 0);
        return acc;
      },
      { interest: 0, principal: 0, preconstruction: 0 }
    );
  }, [properties]);

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        ...form,
        ownership_percent: Number(form.ownership_percent || 0),
        interest_fy: Number(form.interest_fy || 0),
        principal_fy: Number(form.principal_fy || 0),
        preconstruction_interest: Number(form.preconstruction_interest || 0),
        actual_payment_percent: Number(form.actual_payment_percent || 0),
      };
      if (editingId) {
        await apiCall('PUT', `/api/cases/${caseId}/properties/${editingId}`, payload);
      } else {
        await apiCall('POST', `/api/cases/${caseId}/properties`, payload);
      }
      setForm(DEFAULT_FORM);
      setEditingId(null);
      setShowEditor(false);
      setMessage(editingId ? 'Property details updated.' : 'Property details saved.');
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const parseLoanCert = async () => {
    setParsingLoan(true);
    setLoanParsed(null);
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/loan-cert/parse`), { method: 'POST' });
      const payload = await res.json();
      setLoanParsed(payload);
      setShowLoanPanel(true);
    } catch (e) {
      setLoanParsed({ ok: false, error: e.message });
      setShowLoanPanel(true);
    } finally {
      setParsingLoan(false);
    }
  };

  const applyLoanValues = (selfOccupied) => {
    if (!loanParsed?.extracted) return;
    const d = loanParsed.extracted;
    setForm((prev) => ({
      ...prev,
      lender: prev.lender || 'HDFC Bank',
      interest_fy: String(Math.round(d.interest_paid || 0)),
      principal_fy: String(Math.round(d.principal_paid || 0)),
      self_occupied: selfOccupied,
      notes: [prev.notes, `Auto-calculated: Interest ₹${Math.round(d.interest_paid || 0).toLocaleString('en-IN')} | Principal ₹${Math.round(d.principal_paid || 0).toLocaleString('en-IN')} | Loan ${d.loan_account || ''} @ ${d.roi_percent || ''}% (amortization calc)`].filter(Boolean).join('\n'),
    }));
    setShowEditor(true);
    setShowLoanPanel(false);
    setMessage('Loan values pre-filled in editor below. Confirm property type and save.');
  };


  if (error) return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading property data</span></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Building2 className="w-8 h-8 text-primary-600" />
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Property & Home Loan</h1>
            <p className="text-gray-600">Advanced property register with deduction context (Section 24(b), principal tracking, ownership split).</p>
          </div>
        </div>
        {!showEditor ? (
          <button onClick={() => setShowEditor(true)} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2 hover:bg-primary-700">
            <Pencil className="w-4 h-4" /> Add / Edit Property
          </button>
        ) : (
          <button onClick={() => { setShowEditor(false); setEditingId(null); setForm(DEFAULT_FORM); }} className="inline-flex items-center gap-2 rounded-lg bg-gray-200 text-gray-900 px-4 py-2 hover:bg-gray-300">
            <Pencil className="w-4 h-4" /> Close Editor
          </button>
        )}
      </div>

      {message && (
        <div className={`p-3 rounded-lg text-sm ${message.startsWith('Error:') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Properties</p><p className="text-2xl font-bold text-primary-600">{properties.length}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Interest (FY)</p><p className="text-2xl font-bold text-green-600">{inr(totals.interest)}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Principal (FY)</p><p className="text-2xl font-bold text-blue-600">{inr(totals.principal)}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Pre-construction</p><p className="text-2xl font-bold text-orange-600">{inr(totals.preconstruction)}</p></div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-5">
        <h3 className="font-semibold text-blue-900 mb-2">Tax guidance</h3>
        <div className="text-sm text-blue-900 space-y-1">
          <p>🏠 Self-occupied property: Section 24(b) interest deduction capped at <strong>₹2,00,000</strong> per year.</p>
          <p>🏢 Let-out / deemed let-out: <strong>Full interest deductible</strong> under Section 24(b) — no cap. Net loss allowed up to rules.</p>
          <p>🏗️ Under-construction: Pre-construction interest deductible in 5 equal instalments from year of possession.</p>
          <p>💰 Section 80C: Principal repayment deductible up to <strong>₹1,50,000</strong> overall cap (shared with LIC, PPF, ELSS, etc.).</p>
        </div>
      </div>

      {/* Loan Certificate Auto-Read Panel */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary-600" />
            <h2 className="text-base font-semibold text-gray-900">Auto-read from Home Loan Certificate</h2>
          </div>
          <button
            onClick={parseLoanCert}
            disabled={parsingLoan}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 text-white text-sm hover:bg-primary-700 disabled:bg-gray-400"
          >
            {parsingLoan ? <><Loader2 className="w-4 h-4 animate-spin" /> Parsing...</> : <><Sparkles className="w-4 h-4" /> Read Loan Certificate</>}
          </button>
        </div>
        <p className="mt-1 text-sm text-gray-600">
          Calculates interest and principal from the uploaded HDFC loan statement using monthly-rest amortization.
        </p>

        {showLoanPanel && loanParsed && (
          <div className="mt-4 space-y-3">
            {!loanParsed.ok ? (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{loanParsed.error || 'Could not parse loan certificate'}</span>
              </div>
            ) : (
              <>
                {loanParsed.warnings?.length > 0 && (
                  <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                    <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>{loanParsed.warnings[0]}</span>
                  </div>
                )}

                {/* Loan details */}
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm space-y-1">
                  <p><strong>Account:</strong> {loanParsed.extracted?.loan_account} &nbsp;|&nbsp; <strong>Type:</strong> {loanParsed.extracted?.loan_type}</p>
                  <p><strong>Loan Amount:</strong> {inr(loanParsed.extracted?.loan_amount)} &nbsp;|&nbsp; <strong>ROI:</strong> {loanParsed.extracted?.roi_percent}% &nbsp;|&nbsp; <strong>EMI:</strong> {inr(loanParsed.extracted?.current_emi)}</p>
                  <p><strong>EMIs paid this FY:</strong> {loanParsed.extracted?.regular_emi_count} regular + pre-EMI {inr(loanParsed.extracted?.pre_emi_amount)} &nbsp;|&nbsp; <strong>Total paid:</strong> {inr(loanParsed.extracted?.total_paid)}</p>
                </div>

                {/* Calculated interest/principal */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="rounded-lg border border-green-200 bg-green-50 p-3">
                    <p className="text-green-700 text-xs">Interest paid (FY)</p>
                    <p className="text-xl font-bold text-green-800">{inr(loanParsed.extracted?.interest_paid)}</p>
                  </div>
                  <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                    <p className="text-blue-700 text-xs">Principal repaid (FY)</p>
                    <p className="text-xl font-bold text-blue-800">{inr(loanParsed.extracted?.principal_paid)}</p>
                  </div>
                  <div className="rounded-lg border border-purple-200 bg-purple-50 p-3">
                    <p className="text-purple-700 text-xs">Sec 24(b) — self-occ</p>
                    <p className="text-xl font-bold text-purple-800">{inr(loanParsed.deduction_summary?.section_24b_self_occ_limit)} <span className="text-xs font-normal">(cap)</span></p>
                  </div>
                  <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
                    <p className="text-orange-700 text-xs">Sec 80C principal</p>
                    <p className="text-xl font-bold text-orange-800">{inr(loanParsed.deduction_summary?.section_80c_principal_limit)} <span className="text-xs font-normal">(cap)</span></p>
                  </div>
                </div>

                <p className="text-xs text-gray-600">{loanParsed.deduction_summary?.note}</p>

                {/* Apply buttons */}
                <div className="flex flex-wrap gap-3 pt-1">
                  <button
                    onClick={() => applyLoanValues(true)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700"
                  >
                    🏠 Apply as Self-occupied (₹2L interest cap)
                  </button>
                  <button
                    onClick={() => applyLoanValues(false)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 text-white text-sm hover:bg-purple-700"
                  >
                    🏢 Apply as Let-out (full interest)
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>


      {showEditor && (
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Property Editor</h2>
          {editingId ? <p className="text-sm text-blue-700">Editing existing property record #{editingId}</p> : null}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              ['property_name', 'Property Name'],
              ['property_address', 'Property Address'],
              ['ownership_percent', 'Ownership %'],
              ['loan_start_date', 'Loan Start Date'],
              ['possession_date', 'Possession Date'],
              ['lender', 'Lender'],
              ['interest_fy', 'Interest (FY)'],
              ['principal_fy', 'Principal (FY)'],
              ['preconstruction_interest', 'Pre-construction Interest'],
              ['actual_payment_percent', 'Actual Payment %'],
            ].map(([key, title]) => (
              <label key={key} className="block">
                <span className="block text-sm font-medium text-gray-700">{title}</span>
                <input
                  type={key.includes('date') ? 'date' : key.includes('percent') || key.includes('interest') || key.includes('principal') ? 'number' : 'text'}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
                />
              </label>
            ))}
          </div>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.self_occupied} onChange={(e) => setForm({ ...form, self_occupied: e.target.checked })} />
            <span>Self-occupied property</span>
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Notes</span>
            <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-24" />
          </label>
          <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white">
            <Plus className="w-4 h-4" /> {saving ? 'Saving...' : editingId ? 'Update Property' : 'Save Property'}
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Property Register</h2>
        <div className="space-y-3">
          {properties.length === 0 ? (
            <p className="text-sm text-gray-600">No property records yet.</p>
          ) : properties.map((item) => (
            <div key={item.id} className="rounded-lg bg-gray-50 border border-gray-200 p-4">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <p className="font-semibold text-gray-900 flex items-center gap-2">
                    {item.self_occupied ? <Home className="w-4 h-4 text-blue-600" /> : <Landmark className="w-4 h-4 text-purple-600" />}
                    {item.property_name}
                  </p>
                  <p className="text-sm text-gray-600">{item.property_address || '—'}</p>
                </div>
                <PropertyTag item={item} />
              </div>
              <div className="mt-3 grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
                <p><strong>Interest:</strong> {inr(item.interest_fy)}</p>
                <p><strong>Principal:</strong> {inr(item.principal_fy)}</p>
                <p><strong>Ownership:</strong> {Number(item.ownership_percent || 0)}%</p>
                <p><strong>Lender:</strong> {item.lender || '—'}</p>
              </div>
              {item.notes && <p className="mt-2 text-sm text-gray-700"><strong>Notes:</strong> {item.notes}</p>}
              <div className="mt-3">
                <button
                  onClick={() => {
                    setEditingId(item.id);
                    setForm({
                      property_name: item.property_name || '',
                      property_address: item.property_address || '',
                      ownership_percent: String(item.ownership_percent || ''),
                      self_occupied: !!item.self_occupied,
                      possession_date: item.possession_date || '',
                      loan_start_date: item.loan_start_date || '',
                      lender: item.lender || '',
                      interest_fy: String(item.interest_fy || ''),
                      principal_fy: String(item.principal_fy || ''),
                      preconstruction_interest: String(item.preconstruction_interest || ''),
                      actual_payment_percent: String(item.actual_payment_percent || ''),
                      notes: item.notes || '',
                    });
                    setShowEditor(true);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
                >
                  <Pencil className="w-3 h-3" /> Edit record
                </button>
              </div>
              {!item.possession_date && (
                <p className="mt-2 text-xs text-orange-700 inline-flex items-center gap-1">
                  <Hammer className="w-3 h-3" />
                  Possession date missing: keep all under-construction and pre-construction proofs ready.
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
