import { useState } from 'react';
import { BarChart3, Loader2, AlertCircle } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Calculations() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: calcData, error, isLoading } = useSWR(
    apiUrl(`/api/cases/${caseId}/calculations/summary`),
    fetcher
  );

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
        <span>Error loading calculations</span>
      </div>
    );
  }

  const data = calcData?.summary || {};

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="w-8 h-8 text-primary-600" />
        <h1 className="text-3xl font-bold text-gray-900">Calculations</h1>
      </div>

      {/* Income Summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Income Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Income</p>
            <p className="text-2xl font-bold text-blue-600">
              ₹{data.total_income?.toLocaleString() || '0'}
            </p>
          </div>
          <div className="p-4 bg-yellow-50 rounded-lg">
            <p className="text-sm text-gray-600">Total Deductions</p>
            <p className="text-2xl font-bold text-yellow-600">
              ₹{data.total_deductions?.toLocaleString() || '0'}
            </p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Taxable Income</p>
            <p className="text-2xl font-bold text-green-600">
              ₹{data.taxable_income?.toLocaleString() || '0'}
            </p>
          </div>
        </div>
      </div>

      {/* Tax Summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Tax Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-gray-600">Income Tax</p>
            <p className="text-2xl font-bold text-purple-600">
              ₹{data.income_tax?.toLocaleString() || '0'}
            </p>
          </div>
          <div className="p-4 bg-indigo-50 rounded-lg">
            <p className="text-sm text-gray-600">Total TDS</p>
            <p className="text-2xl font-bold text-indigo-600">
              ₹{data.total_tds?.toLocaleString() || '0'}
            </p>
          </div>
          <div className="p-4 bg-red-50 rounded-lg">
            <p className="text-sm text-gray-600">Balance Due/Refund</p>
            <p className="text-2xl font-bold text-red-600">
              ₹{data.balance_due?.toLocaleString() || '0'}
            </p>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
          Use this page as your computation truth layer. If values look off, update Income / Tax Credits / Property first, then return here.
          For final filing decision and form checks, go to <a href="/review" className="underline font-semibold">Review</a>.
        </div>
      </div>

      {/* Income Breakdown */}
      {data.income_breakdown && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Income Breakdown</h2>
          <div className="space-y-2">
            {Object.entries(data.income_breakdown).map(([key, value]) => (
              <div key={key} className="flex justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">{key}</span>
                <span className="font-semibold text-gray-900">
                  ₹{value?.toLocaleString() || '0'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
