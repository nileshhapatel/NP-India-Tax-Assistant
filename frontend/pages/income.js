import { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, AlertCircle, DollarSign, TrendingUp } from 'lucide-react';
import useSWR from 'swr';

const fetcher = (url) => fetch(url).then((res) => res.json());

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
  const [selectedCase, setSelectedCase] = useState(1); // Default to Nilesh's case
  const { data: incomeData, isLoading, error, mutate } = useSWR(
    selectedCase ? `/api/cases/${selectedCase}/income` : null,
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
      setMessage('❌ Please enter a valid amount');
      return;
    }

    setAdding(true);
    try {
      const res = await fetch(`/api/cases/${selectedCase}/income`, {
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
      if (result.ok) {
        setMessage('✅ Income entry added');
        setNewEntry({
          income_type: 'salary_india',
          amount: '',
          tds_deducted: '',
          fiscal_year: '2025-26',
        });
        mutate();
        setTimeout(() => setMessage(''), 3000);
      } else {
        setMessage('❌ Error: ' + (result.error || 'Unknown error'));
      }
    } catch (err) {
      setMessage('❌ Error: ' + err.message);
    }
    setAdding(false);
  };

  const handleDelete = async (incomeId) => {
    if (!window.confirm('Delete this income entry?')) return;

    try {
      const res = await fetch(`/api/cases/${selectedCase}/income/${incomeId}`, {
        method: 'DELETE',
      });
      const result = await res.json();
      if (result.ok) {
        setMessage('✅ Income entry deleted');
        mutate();
        setTimeout(() => setMessage(''), 3000);
      } else {
        setMessage('❌ Error: ' + (result.error || 'Unknown error'));
      }
    } catch (err) {
      setMessage('❌ Error: ' + err.message);
    }
  };

  const entries = incomeData?.income_entries || [];
  const totalIncome = entries.reduce((sum, e) => sum + (e.gross_amount || 0), 0);
  const totalTDS = entries.reduce((sum, e) => sum + (e.tds_amount || 0), 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">💰 Income Management</h1>
        <p className="text-lg text-gray-600">Add and track all sources of income for AY 2026-27</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Income</p>
              <p className="text-3xl font-bold text-primary-600">₹{(totalIncome / 100000).toFixed(2)}L</p>
            </div>
            <DollarSign className="w-12 h-12 text-primary-100" />
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">TDS Deducted</p>
              <p className="text-3xl font-bold text-success-600">₹{(totalTDS / 100000).toFixed(2)}L</p>
            </div>
            <TrendingUp className="w-12 h-12 text-success-100" />
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Net Income (after TDS)</p>
              <p className="text-3xl font-bold text-blue-600">₹{((totalIncome - totalTDS) / 100000).toFixed(2)}L</p>
            </div>
            <TrendingUp className="w-12 h-12 text-blue-100" />
          </div>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`card p-4 border ${message.includes('✅') ? 'border-success-300 bg-success-50' : 'border-danger-300 bg-danger-50'}`}>
          <p className={message.includes('✅') ? 'text-success-700' : 'text-danger-700'}>{message}</p>
        </div>
      )}

      {/* Add Income Entry */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Plus className="w-6 h-6 text-primary-600" />
          Add Income Entry
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Income Type</label>
            <select
              value={newEntry.income_type}
              onChange={(e) => setNewEntry({ ...newEntry, income_type: e.target.value })}
              className="input w-full"
            >
              {INCOME_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Gross Amount (₹)</label>
            <input
              type="number"
              value={newEntry.amount}
              onChange={(e) => setNewEntry({ ...newEntry, amount: e.target.value })}
              placeholder="0"
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">TDS Deducted (₹)</label>
            <input
              type="number"
              value={newEntry.tds_deducted}
              onChange={(e) => setNewEntry({ ...newEntry, tds_deducted: e.target.value })}
              placeholder="0"
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Fiscal Year</label>
            <select
              value={newEntry.fiscal_year}
              onChange={(e) => setNewEntry({ ...newEntry, fiscal_year: e.target.value })}
              className="input w-full"
            >
              <option value="2025-26">FY 2025-26</option>
              <option value="2024-25">FY 2024-25</option>
              <option value="2023-24">FY 2023-24</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleAddIncome}
              disabled={adding}
              className="btn-primary w-full"
            >
              {adding ? 'Adding...' : 'Add Entry'}
            </button>
          </div>
        </div>
      </div>

      {/* Income Entries List */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Income Entries (FY 2025-26)</h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 p-4 bg-danger-50 border border-danger-300 rounded-lg">
            <AlertCircle className="w-5 h-5 text-danger-600 mt-0.5" />
            <p className="text-danger-700">Failed to load income entries</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">No income entries yet</p>
            <p className="text-sm text-gray-500">Add your first income source above</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Income Type</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">Gross Amount</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">TDS Deducted</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">Net Amount</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Action</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">{entry.income_type}</td>
                    <td className="py-3 px-4 text-right font-semibold text-gray-900">₹{(entry.gross_amount || 0).toLocaleString()}</td>
                    <td className="py-3 px-4 text-right text-success-600">₹{(entry.tds_amount || 0).toLocaleString()}</td>
                    <td className="py-3 px-4 text-right text-primary-600">₹{((entry.gross_amount || 0) - (entry.tds_amount || 0)).toLocaleString()}</td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => handleDelete(entry.id)}
                        className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 p-1 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Validation & Reconciliation CTA */}
      {entries.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-8">
          <h3 className="text-2xl font-bold text-gray-900 mb-4">📊 Next Step: Reconciliation</h3>
          <p className="text-gray-700 mb-6">
            You've entered ₹{(totalIncome / 100000).toFixed(2)}L in income. Now upload your AIS and Form 26AS to verify these amounts match official government records.
          </p>
          <a href="/reconciliation">
            <button className="btn-primary">
              Continue to Reconciliation →
            </button>
          </a>
        </div>
      )}

      {/* Help Section */}
      <div className="bg-gradient-to-r from-primary-600 to-blue-600 rounded-xl p-8 text-white">
        <h3 className="text-2xl font-bold mb-4">💡 Income Entry Tips</h3>
        <ul className="space-y-3">
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Salary:</strong> Use your gross salary (before tax). Include both India-source and foreign salary separately.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Interest:</strong> Separate savings account interest from fixed deposits, bonds, and other interest sources.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Dividends:</strong> Include dividends from stocks and mutual funds. TDS may already be deducted.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>TDS:</strong> Always record TDS deducted at source. This will be reconciled against Form 26AS.
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">💰 Income Management</h1>
        <p className="text-lg text-gray-600">Add and track all sources of income for AY 2026-27</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Income</p>
              <p className="text-3xl font-bold text-primary-600">₹{(totalIncome / 100000).toFixed(2)}L</p>
            </div>
            <DollarSign className="w-12 h-12 text-primary-100" />
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">TDS Deducted</p>
              <p className="text-3xl font-bold text-success-600">₹{(totalTDS / 100000).toFixed(2)}L</p>
            </div>
            <TrendingUp className="w-12 h-12 text-success-100" />
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Net Income (after TDS)</p>
              <p className="text-3xl font-bold text-blue-600">₹{((totalIncome - totalTDS) / 100000).toFixed(2)}L</p>
            </div>
            <TrendingUp className="w-12 h-12 text-blue-100" />
          </div>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div className={`card p-4 border ${message.includes('✅') ? 'border-success-300 bg-success-50' : 'border-danger-300 bg-danger-50'}`}>
          <p className={message.includes('✅') ? 'text-success-700' : 'text-danger-700'}>{message}</p>
        </div>
      )}

      {/* Add Income Entry */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Plus className="w-6 h-6 text-primary-600" />
          Add Income Entry
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Income Type</label>
            <select
              value={newEntry.income_type}
              onChange={(e) => setNewEntry({ ...newEntry, income_type: e.target.value })}
              className="input w-full"
            >
              {INCOME_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Gross Amount (₹)</label>
            <input
              type="number"
              value={newEntry.amount}
              onChange={(e) => setNewEntry({ ...newEntry, amount: e.target.value })}
              placeholder="0"
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">TDS Deducted (₹)</label>
            <input
              type="number"
              value={newEntry.tds_deducted}
              onChange={(e) => setNewEntry({ ...newEntry, tds_deducted: e.target.value })}
              placeholder="0"
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Fiscal Year</label>
            <select
              value={newEntry.fiscal_year}
              onChange={(e) => setNewEntry({ ...newEntry, fiscal_year: e.target.value })}
              className="input w-full"
            >
              <option value="2025-26">FY 2025-26</option>
              <option value="2024-25">FY 2024-25</option>
              <option value="2023-24">FY 2023-24</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleAddIncome}
              disabled={adding}
              className="btn-primary w-full"
            >
              {adding ? 'Adding...' : 'Add Entry'}
            </button>
          </div>
        </div>
      </div>

      {/* Income Entries List */}
      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Income Entries (FY 2025-26)</h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
          </div>
        ) : error ? (
          <div className="flex items-start gap-3 p-4 bg-danger-50 border border-danger-300 rounded-lg">
            <AlertCircle className="w-5 h-5 text-danger-600 mt-0.5" />
            <p className="text-danger-700">Failed to load income entries</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600 mb-4">No income entries yet</p>
            <p className="text-sm text-gray-500">Add your first income source above</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Income Type</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">Gross Amount</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">TDS Deducted</th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">Net Amount</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Action</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">{entry.income_type}</td>
                    <td className="py-3 px-4 text-right font-semibold text-gray-900">₹{(entry.gross_amount || 0).toLocaleString()}</td>
                    <td className="py-3 px-4 text-right text-success-600">₹{(entry.tds_deducted || 0).toLocaleString()}</td>
                    <td className="py-3 px-4 text-right text-primary-600">₹{((entry.gross_amount || 0) - (entry.tds_deducted || 0)).toLocaleString()}</td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => handleDelete(entry.id)}
                        className="text-danger-600 hover:text-danger-700 hover:bg-danger-50 p-1 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Validation & Reconciliation CTA */}
      {entries.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-8">
          <h3 className="text-2xl font-bold text-gray-900 mb-4">📊 Next Step: Reconciliation</h3>
          <p className="text-gray-700 mb-6">
            You've entered ₹{(totalIncome / 100000).toFixed(2)}L in income. Now upload your AIS and Form 26AS to verify these amounts match official government records.
          </p>
          <a href="/reconciliation">
            <button className="btn-primary">
              Continue to Reconciliation →
            </button>
          </a>
        </div>
      )}

      {/* Help Section */}
      <div className="bg-gradient-to-r from-primary-600 to-blue-600 rounded-xl p-8 text-white">
        <h3 className="text-2xl font-bold mb-4">💡 Income Entry Tips</h3>
        <ul className="space-y-3">
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Salary:</strong> Use your gross salary (before tax). Include both India-source and foreign salary separately.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Interest:</strong> Separate savings account interest from fixed deposits, bonds, and other interest sources.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>Dividends:</strong> Include dividends from stocks and mutual funds. TDS may already be deducted.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="font-bold">•</span>
            <span>
              <strong>TDS:</strong> Always record TDS deducted at source. This will be reconciled against Form 26AS.
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
