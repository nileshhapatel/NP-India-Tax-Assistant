import { useState } from 'react';
import { Plus, Trash2, Loader2, AlertCircle, DollarSign, Info } from 'lucide-react';
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

export default function Income() {
  const { selectedCaseId, selectedCase } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: incomeData, isLoading, error, mutate } = useSWR(
    apiUrl(`/api/cases/${caseId}/income`),
    fetcher
  );

  const [newEntry, setNewEntry] = useState({
    income_type: 'salary_india',
    amount: '',
    tds_deducted: '',
    fiscal_year: '2025-26',
  });
  const [message, setMessage] = useState('');
  const [adding, setAdding] = useState(false);

  const handleAddIncome = async () => {
    if (!newEntry.amount || parseFloat(newEntry.amount) <= 0) {
      setMessage('Please enter a valid income amount.');
      return;
    }
    setAdding(true);
    try {
      const res = await fetch(apiUrl(`/api/cases/${caseId}/income`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          income_type: newEntry.income_type,
          amount: parseFloat(newEntry.amount),
          tds_deducted: parseFloat(newEntry.tds_deducted) || 0,
          fiscal_year: newEntry.fiscal_year,
        }),
      });
      const result = await res.json();
      if (!res.ok || !result.ok) throw new Error(result.error || `Failed (${res.status})`);
      setMessage('Income entry added.');
      setNewEntry((prev) => ({ ...prev, amount: '', tds_deducted: '' }));
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

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  }
  if (error) {
    return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading income data</span></div>;
  }

  const entries = incomeData?.income_entries || [];
  const totalIncome = entries.reduce((sum, e) => sum + (parseFloat(e.gross_amount) || 0), 0);
  const totalTds = entries.reduce((sum, e) => sum + (parseFloat(e.tds_amount) || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <DollarSign className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Income Register</h1>
          <p className="text-gray-600">Case {caseId} • FY {selectedCase?.financial_year || '—'} • Add all taxable heads before reconciliation.</p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900 flex items-start gap-2">
        <Info className="w-4 h-4 mt-0.5" />
        Enter source-wise values that match statements/AIS. Keep TDS exactly aligned to Form 26AS entries for clean matching.
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Add Income Entry</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Income Type</span>
            <select value={newEntry.income_type} onChange={(e) => setNewEntry({ ...newEntry, income_type: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg">
              {INCOME_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Amount (₹)</span>
            <input type="number" value={newEntry.amount} onChange={(e) => setNewEntry({ ...newEntry, amount: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">TDS (₹)</span>
            <input type="number" value={newEntry.tds_deducted} onChange={(e) => setNewEntry({ ...newEntry, tds_deducted: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Fiscal Year</span>
            <input type="text" value={newEntry.fiscal_year} onChange={(e) => setNewEntry({ ...newEntry, fiscal_year: e.target.value })} className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg" />
          </label>
        </div>
        <button onClick={handleAddIncome} disabled={adding} className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400">
          <Plus className="w-4 h-4" />
          {adding ? 'Adding...' : 'Add Entry'}
        </button>
        {message && <div className={`mt-4 p-3 rounded-lg text-sm ${message.startsWith('Error:') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{message}</div>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-200"><p className="text-sm text-gray-600">Total Income</p><p className="text-2xl font-bold text-blue-600">₹{totalIncome.toLocaleString()}</p></div>
        <div className="p-4 bg-green-50 rounded-lg border border-green-200"><p className="text-sm text-gray-600">Total TDS</p><p className="text-2xl font-bold text-green-600">₹{totalTds.toLocaleString()}</p></div>
        <div className="p-4 bg-purple-50 rounded-lg border border-purple-200"><p className="text-sm text-gray-600">Entries</p><p className="text-2xl font-bold text-purple-600">{entries.length}</p></div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Income Entries</h2>
        <div className="space-y-2">
          {entries.length === 0 ? (
            <p className="text-gray-600 text-sm">No income entries yet.</p>
          ) : (
            entries.map((entry) => (
              <div key={entry.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-semibold text-gray-900">{entry.income_type}</p>
                  <p className="text-sm text-gray-600">₹{parseFloat(entry.gross_amount || 0).toLocaleString()} | TDS: ₹{parseFloat(entry.tds_amount || 0).toLocaleString()}</p>
                </div>
                <button onClick={() => handleDelete(entry.id)} className="text-red-600 hover:text-red-700">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

