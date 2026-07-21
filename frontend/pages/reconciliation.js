import { useState } from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, TrendingUp, BarChart3, FileText } from 'lucide-react';
import useSWR from 'swr';

const fetcher = (url) => fetch(url).then((res) => res.json());

export default function Reconciliation() {
  const [selectedCase, setSelectedCase] = useState(1);
  const { data: reconcilData, isLoading, error } = useSWR(
    selectedCase ? `/api/cases/${selectedCase}/reconciliation` : null,
    fetcher
  );

  const recon = reconcilData?.reconciliation || {};
  const isMatched = recon.status === 'matched';

  const formatCurrency = (num) => {
    return (num / 100000).toFixed(2);
  };

  const getVarianceIcon = (variance) => {
    if (Math.abs(variance) < 100) return <CheckCircle2 className="w-5 h-5 text-success-600" />;
    if (Math.abs(variance) < 1000) return <AlertTriangle className="w-5 h-5 text-warning-600" />;
    return <AlertCircle className="w-5 h-5 text-danger-600" />;
  };

  const getVarianceColor = (variance) => {
    if (Math.abs(variance) < 100) return 'bg-success-50 border-success-300';
    if (Math.abs(variance) < 1000) return 'bg-warning-50 border-warning-300';
    return 'bg-danger-50 border-danger-300';
  };

  const getVarianceText = (variance) => {
    if (Math.abs(variance) < 100) return '✅ Matched';
    if (Math.abs(variance) < 1000) return '⚠️ Minor variance';
    return '❌ Significant variance';
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">🔍 Three-Way Reconciliation</h1>
        <p className="text-lg text-gray-600">Match your income entries with AIS, Form 26AS, and ITR calculations</p>
      </div>

      {/* Reconciliation Flow Diagram */}
      <div className="card p-8">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Reconciliation Process</h2>
        <div className="flex items-center justify-between gap-4 flex-wrap md:flex-nowrap">
          <div className="flex-1 text-center p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="text-3xl mb-2">📝</div>
            <p className="font-semibold text-gray-900">Your Entries</p>
            <p className="text-sm text-gray-600 mt-2">Income you've recorded in the app</p>
          </div>

          <div className="hidden md:flex items-center justify-center text-2xl text-gray-400">↔️</div>

          <div className="flex-1 text-center p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="text-3xl mb-2">📊</div>
            <p className="font-semibold text-gray-900">AIS & 26AS</p>
            <p className="text-sm text-gray-600 mt-2">Government-reported income & TDS</p>
          </div>

          <div className="hidden md:flex items-center justify-center text-2xl text-gray-400">↔️</div>

          <div className="flex-1 text-center p-4 bg-purple-50 rounded-lg border border-purple-200">
            <div className="text-3xl mb-2">🧮</div>
            <p className="font-semibold text-gray-900">ITR Calculation</p>
            <p className="text-sm text-gray-600 mt-2">Computed tax liability</p>
          </div>
        </div>
      </div>

      {/* Main Reconciliation Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-40">
          <p className="text-gray-600">Loading reconciliation data...</p>
        </div>
      ) : error ? (
        <div className="card p-6 bg-danger-50 border border-danger-300">
          <AlertCircle className="w-5 h-5 text-danger-600 mb-2" />
          <p className="text-danger-700">Failed to load reconciliation data</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Gross Income Reconciliation */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary-600" />
              Gross Income Reconciliation
            </h3>

            <div className="space-y-4">
              <div className={`p-4 rounded-lg border ${getVarianceColor(recon.variances?.source_vs_ais || 0)}`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Your Entries vs AIS</p>
                    <p className="text-2xl font-bold text-gray-900">₹{formatCurrency(recon.source_total || 0)}L</p>
                    <p className="text-xs text-gray-500 mt-1">vs AIS: ₹{formatCurrency(recon.ais_reported || 0)}L</p>
                  </div>
                  {getVarianceIcon(recon.variances?.source_vs_ais || 0)}
                </div>
                <div className="text-sm font-medium">
                  {getVarianceText(recon.variances?.source_vs_ais || 0)}
                </div>
                {Math.abs(recon.variances?.source_vs_ais || 0) > 100 && (
                  <p className="text-xs text-gray-600 mt-2">
                    Variance: ₹{(recon.variances?.source_vs_ais || 0).toLocaleString()}
                  </p>
                )}
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-gray-700">
                  <strong>Reason:</strong> Your income entries should match the total shown in AIS (Annual Information Statement). If different, check for:
                </p>
                <ul className="text-xs text-gray-600 mt-2 space-y-1 list-disc list-inside">
                  <li>Missing income sources</li>
                  <li>Incorrect amounts</li>
                  <li>Income reported under different head</li>
                  <li>Spouse's income (if filing separately)</li>
                </ul>
              </div>
            </div>
          </div>

          {/* TDS Reconciliation */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-success-600" />
              TDS Reconciliation
            </h3>

            <div className="space-y-4">
              <div className={`p-4 rounded-lg border ${getVarianceColor(recon.variances?.form26as_vs_itr || 0)}`}>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-sm text-gray-600 mb-1">Form 26AS TDS</p>
                    <p className="text-2xl font-bold text-gray-900">₹{formatCurrency(recon.form26as_tds || 0)}L</p>
                    <p className="text-xs text-gray-500 mt-1">Your entries: ₹{formatCurrency(recon.form26as_tds || 0)}L</p>
                  </div>
                  {getVarianceIcon(recon.variances?.form26as_vs_itr || 0)}
                </div>
                <div className="text-sm font-medium">
                  {getVarianceText(recon.variances?.form26as_vs_itr || 0)}
                </div>
              </div>

              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <p className="text-sm text-gray-700">
                  <strong>Important:</strong> Form 26AS shows all tax credits reported by banks, employers, and brokers. This must match your entries.
                </p>
                <p className="text-xs text-gray-600 mt-2">
                  If variance exists, contact institutions to verify TDS reported.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tax Calculation Summary */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-orange-600" />
          Tax Calculation Summary
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg border border-blue-200">
            <p className="text-sm text-gray-600">Gross Income</p>
            <p className="text-2xl font-bold text-blue-900">₹{formatCurrency(recon.source_total || 0)}L</p>
          </div>

          <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 rounded-lg border border-green-200">
            <p className="text-sm text-gray-600">Total TDS</p>
            <p className="text-2xl font-bold text-green-900">₹{formatCurrency(recon.form26as_tds || 0)}L</p>
          </div>

          <div className="p-4 bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg border border-purple-200">
            <p className="text-sm text-gray-600">Tax Liability</p>
            <p className="text-2xl font-bold text-purple-900">₹{formatCurrency(recon.calculated_tax || 0)}L</p>
          </div>

          <div className="p-4 bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg border border-orange-200">
            <p className="text-sm text-gray-600">Tax Due / Refund</p>
            <p className={`text-2xl font-bold ${(recon.calculated_tax || 0) > (recon.form26as_tds || 0) ? 'text-orange-900' : 'text-success-900'}`}>
              ₹{formatCurrency((recon.calculated_tax || 0) - (recon.form26as_tds || 0))}L
            </p>
          </div>
        </div>
      </div>

      {/* Compliance Checklist */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">✅ Reconciliation Checklist</h3>

        <div className="space-y-3">
          {[
            { text: 'All income sources identified', done: !!recon.source_total },
            { text: 'AIS downloaded from portal', done: Math.abs(recon.variances?.source_vs_ais || 0) < 100 },
            { text: 'Form 26AS downloaded', done: !!recon.form26as_tds },
            { text: 'TDS entries verified', done: Math.abs(recon.variances?.form26as_vs_itr || 0) < 100 },
            { text: 'Tax calculation complete', done: !!recon.calculated_tax },
          ].map((item, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <div className={`w-5 h-5 rounded flex items-center justify-center ${item.done ? 'bg-success-600' : 'bg-gray-300'}`}>
                {item.done && <span className="text-white text-sm">✓</span>}
              </div>
              <span className={item.done ? 'text-success-700 font-medium' : 'text-gray-600'}>{item.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* AI Expert Help */}
      <div className="bg-gradient-to-r from-primary-600 to-blue-600 rounded-xl p-8 text-white">
        <h3 className="text-2xl font-bold mb-4">🤖 AI Reconciliation Expert</h3>
        <p className="mb-6">
          Large variances? Get AI-powered explanations of discrepancies with government rules, common causes, and remediation steps.
        </p>
        <button className="bg-white text-primary-600 font-medium px-6 py-2 rounded-lg hover:bg-blue-50 transition">
          Get AI Explanation →
        </button>
      </div>

      {/* Final Steps */}
      <div className="card p-6 border-2 border-success-300 bg-success-50">
        <h3 className="text-lg font-bold text-success-900 mb-3">✅ Ready to File?</h3>
        <p className="text-success-800 mb-4">
          After reconciliation is complete and all variances are resolved, you're ready to generate your final ITR and export for filing on the official portal.
        </p>
        <a href="/review">
          <button className="btn-primary">
            Continue to Final Review →
          </button>
        </a>
      </div>
    </div>
  );
}
