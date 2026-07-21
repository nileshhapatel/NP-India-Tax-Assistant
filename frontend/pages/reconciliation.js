import { useState } from 'react';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Reconciliation() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: reconcData, error, isLoading, mutate } = useSWR(
    apiUrl(`/api/cases/${caseId}/reconciliation`),
    fetcher
  );

  const [activeTab, setActiveTab] = useState('overview');

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-red-600">
        <AlertCircle className="w-6 h-6" />
        <span>Error loading reconciliation data</span>
      </div>
    );
  }

  const data = reconcData?.reconciliation || {};
  const discrepancies = data.discrepancies || [];
  const reconcStatus = data.risk_rating || 'pending';
  const riskClass = reconcStatus === 'high' ? 'text-red-700 bg-red-50 border-red-200' : reconcStatus === 'medium' ? 'text-yellow-700 bg-yellow-50 border-yellow-200' : 'text-green-700 bg-green-50 border-green-200';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <CheckCircle className="w-8 h-8 text-primary-600" />
        <h1 className="text-3xl font-bold text-gray-900">3-Way Reconciliation</h1>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="flex gap-4 px-6">
          {['overview', 'sources', 'discrepancies'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-4 px-2 border-b-2 font-semibold transition ${
                activeTab === tab
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Reconciliation Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-gray-600">Source Amount</p>
              <p className="text-2xl font-bold text-blue-600">
                ₹{data.total_source?.toLocaleString() || '0'}
              </p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-sm text-gray-600">AIS Amount</p>
              <p className="text-2xl font-bold text-green-600">
                ₹{data.total_ais?.toLocaleString() || '0'}
              </p>
            </div>
            <div className="p-4 bg-purple-50 rounded-lg">
              <p className="text-sm text-gray-600">ITR Amount</p>
              <p className="text-2xl font-bold text-purple-600">
                ₹{data.total_itr?.toLocaleString() || '0'}
              </p>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-lg bg-green-50 border border-green-200">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className={`font-semibold px-2 py-1 rounded border ${riskClass}`}>Risk Rating: {reconcStatus}</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
            <a href="/documents" className="rounded-lg border border-gray-300 px-3 py-2 hover:bg-gray-50">Check supporting documents</a>
            <a href="/income" className="rounded-lg border border-gray-300 px-3 py-2 hover:bg-gray-50">Adjust source income entries</a>
            <a href="/tax-credits" className="rounded-lg border border-gray-300 px-3 py-2 hover:bg-gray-50">Reconcile TDS / credits</a>
          </div>
        </div>
      )}

      {/* Sources Tab */}
      {activeTab === 'sources' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Source Documents</h2>
          <div className="space-y-3">
            {data.sources?.length === 0 ? (
              <p className="text-gray-600 text-sm">No sources added yet</p>
            ) : (
              data.sources?.map((source, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <div className="flex justify-between">
                    <span className="font-semibold text-gray-900">{source.name}</span>
                    <span className="text-gray-600">₹{source.amount?.toLocaleString() || '0'}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{source.description}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Discrepancies Tab */}
      {activeTab === 'discrepancies' && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Discrepancies</h2>
          <div className="space-y-3">
            {discrepancies.length === 0 ? (
              <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                <p className="text-green-900 font-semibold">✓ No discrepancies found</p>
              </div>
            ) : (
              discrepancies.map((disc, i) => (
                <div
                  key={i}
                  className={`p-4 rounded-lg border ${
                    disc.severity === 'error'
                      ? 'bg-red-50 border-red-200'
                      : 'bg-yellow-50 border-yellow-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <AlertCircle
                      className={`w-5 h-5 mt-0.5 ${
                        disc.severity === 'error' ? 'text-red-600' : 'text-yellow-600'
                      }`}
                    />
                    <div>
                      <p className="font-semibold text-gray-900">{disc.title}</p>
                      <p className="text-sm text-gray-700 mt-1">{disc.description}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
