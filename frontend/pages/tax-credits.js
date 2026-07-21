import { useEffect, useState } from 'react';
import { BadgeIndianRupee, Loader2, AlertCircle, Plus, CheckCircle2, ExternalLink } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const DEFAULT_FORM = {
  deductor: '',
  credit_type: 'TDS',
  section_code: '',
  gross_amount_26as: '',
  tax_amount_26as: '',
  tax_claimed: '',
  notes: '',
};

export default function TaxCredits() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, error, isLoading, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/tax-credits`), fetcher);
  const { data: referenceData } = useSWR(apiUrl('/api/reference/tax-credits'), fetcher);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => setForm(DEFAULT_FORM), []);

  const addCredit = async () => {
    setSaving(true);
    try {
      await apiCall('POST', `/api/cases/${caseId}/tax-credits`, {
        ...form,
        gross_amount_26as: Number(form.gross_amount_26as || 0),
        tax_amount_26as: Number(form.tax_amount_26as || 0),
        tax_claimed: Number(form.tax_claimed || 0),
      });
      setForm(DEFAULT_FORM);
      await mutate();
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (error) return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading tax credits</span></div>;

  const credits = data?.credits || [];
  const references = referenceData?.sections || [];
  const govLinks = referenceData?.gov_links || [];
  const total26as = credits.reduce((sum, item) => sum + (item.tax_amount_26as || 0), 0);
  const totalClaimed = credits.reduce((sum, item) => sum + (item.tax_claimed || 0), 0);
  const netDelta = total26as - totalClaimed;
  const hasMismatch = Math.abs(netDelta) > 0.5;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <BadgeIndianRupee className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Tax Credits</h1>
          <p className="text-gray-600">Track TDS/TCS/advance-tax claims with Form 26AS reconciliation and government references.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Entries</p><p className="text-2xl font-bold text-primary-600">{credits.length}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">26AS Tax</p><p className="text-2xl font-bold text-green-600">₹{total26as.toLocaleString()}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Claimed</p><p className="text-2xl font-bold text-purple-600">₹{totalClaimed.toLocaleString()}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Unclaimed / Excess</p><p className={`text-2xl font-bold ${hasMismatch ? (netDelta > 0 ? 'text-orange-600' : 'text-red-600') : 'text-green-600'}`}>₹{Math.abs(netDelta).toLocaleString()}</p></div>
      </div>

      {hasMismatch && (
        <div className={`rounded-lg border p-4 text-sm ${netDelta > 0 ? 'border-orange-200 bg-orange-50 text-orange-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
          {netDelta > 0
            ? `You still have ₹${Math.abs(netDelta).toLocaleString()} credit in 26AS not yet claimed in this register.`
            : `Claimed credits exceed 26AS by ₹${Math.abs(netDelta).toLocaleString()}. Recheck deductor entries and challans.`}
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 space-y-3">
        <h3 className="font-semibold text-blue-900">How to claim credits correctly</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-blue-900">
          {references.map((ref) => (
            <div key={ref.code} className="rounded-lg bg-white border border-blue-200 p-3">
              <p className="font-semibold">{ref.code}</p>
              <p>{ref.how_claimed}</p>
              <p className="mt-1"><strong>Important:</strong> {ref.important}</p>
            </div>
          ))}
        </div>
        {govLinks.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {govLinks.map((link) => (
              <a key={link} href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-xs text-white hover:bg-blue-700">
                Govt reference <ExternalLink className="w-3 h-3" />
              </a>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {['deductor', 'section_code', 'gross_amount_26as', 'tax_amount_26as', 'tax_claimed'].map((key) => (
            <label key={key} className="block">
              <span className="block text-sm font-medium text-gray-700">{key.replace(/_/g, ' ')}</span>
              <input
                type={key.includes('amount') ? 'number' : 'text'}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              />
            </label>
          ))}
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Credit Type</span>
            <select value={form.credit_type} onChange={(e) => setForm({ ...form, credit_type: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
              <option value="TDS">TDS</option>
              <option value="TCS">TCS</option>
              <option value="Advance Tax">Advance Tax</option>
              <option value="Self Assessment Tax">Self Assessment Tax</option>
            </select>
          </label>
        </div>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700">Notes</span>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-24" />
        </label>
        <button onClick={addCredit} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white">
          <Plus className="w-4 h-4" /> {saving ? 'Saving...' : 'Add Credit'}
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Credit Register</h2>
        <div className="space-y-3">
          {credits.length === 0 ? (
            <p className="text-sm text-gray-600">No credits added yet.</p>
          ) : credits.map((credit) => (
            <div key={credit.id} className="rounded-lg bg-gray-50 border border-gray-200 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-semibold text-gray-900">{credit.deductor}</p>
                  <p className="text-sm text-gray-600">{credit.credit_type} • {credit.section_code || '—'}</p>
                </div>
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              </div>
              <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-sm text-gray-700">
                <p>26AS: ₹{Number(credit.tax_amount_26as || 0).toLocaleString()}</p>
                <p>Claimed: ₹{Number(credit.tax_claimed || 0).toLocaleString()}</p>
                <p>Gross: ₹{Number(credit.gross_amount_26as || 0).toLocaleString()}</p>
              </div>
              {Number(credit.tax_claimed || 0) > Number(credit.tax_amount_26as || 0) && (
                <p className="mt-2 text-xs text-red-700">Claimed exceeds 26AS entry. Reconcile before filing.</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
