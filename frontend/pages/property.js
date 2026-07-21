import { useMemo, useState } from 'react';
import { Building2, Loader2, AlertCircle, Plus, Pencil, Landmark, Home, Hammer } from 'lucide-react';
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

const inr = (v) => `₹${Number(v || 0).toLocaleString('en-IN')}`;

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

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
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
          <p>🏠 Self-occupied property: Interest under Section 24(b) is generally capped (commonly up to ₹2 lakh, subject to conditions).</p>
          <p>🏢 Let-out property: Interest treatment differs; maintain rent/municipal tax/interest evidence for accurate computation.</p>
          <p>🏗️ Under-construction interest: track pre-construction interest carefully for phased claim after possession.</p>
        </div>
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
