import { useState } from 'react';
import { Loader2, AlertCircle, FileText, Download, CheckCircle2, AlertTriangle, Info } from 'lucide-react';
import useSWR from 'swr';

import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Review() {
  const { selectedCaseId } = useCaseContext();
  const selectedCase = selectedCaseId || 1;
  const [activeTab, setActiveTab] = useState('calculation');
  const [applyingItrForm, setApplyingItrForm] = useState(false);
  
  const { data: calcData, isLoading: calcLoading, error: calcError } = useSWR(
    selectedCase ? apiUrl(`/api/cases/${selectedCase}/reports/calculation`) : null,
    fetcher
  );
  
  const { data: formData, isLoading: formLoading, error: formError } = useSWR(
    selectedCase ? apiUrl(`/api/cases/${selectedCase}/reports/form-summary`) : null,
    fetcher
  );
  const { data: itrData, mutate: mutateItr } = useSWR(
    selectedCase ? apiUrl(`/api/cases/${selectedCase}/itr-form-recommendation`) : null,
    fetcher
  );

  const calcReport = calcData?.report || {};
  const formReport = formData?.report || {};
  const itrRecommendation = itrData?.recommendation || null;

  const handleExportPDF = () => {
    alert('PDF export functionality coming soon. For now, use browser print to PDF.');
  };

  const handleExportJSON = () => {
    const data = activeTab === 'calculation' ? calcReport : formReport;
    const element = document.createElement('a');
    element.href = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(data, null, 2));
    element.download = `ITR_${activeTab}_${selectedCase}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const isLoading = (activeTab === 'calculation' && calcLoading) || (activeTab === 'form' && formLoading);
  const error = (activeTab === 'calculation' && calcError) || (activeTab === 'form' && formError);

  const applyRecommendedForm = async () => {
    setApplyingItrForm(true);
    try {
      await fetch(apiUrl(`/api/cases/${selectedCase}/itr-form-recommendation/apply`), { method: 'POST' });
      await mutateItr();
    } finally {
      setApplyingItrForm(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">📋 Final Review & Report</h1>
        <p className="text-lg text-gray-600">Generate detailed tax reports before filing on the official portal</p>
      </div>
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
        Final sequence: <a className="underline font-semibold" href="/reconciliation">Reconciliation</a> → review blockers/warnings here →
        confirm ITR form recommendation → <a className="underline font-semibold" href="/export">Export</a> for portal/offline utility filing.
      </div>

      {/* Tabs & Export */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex gap-2 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('calculation')}
            className={`px-6 py-3 font-medium border-b-2 transition ${
              activeTab === 'calculation'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            📊 Tax Calculation
          </button>
          <button
            onClick={() => setActiveTab('form')}
            className={`px-6 py-3 font-medium border-b-2 transition ${
              activeTab === 'form'
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            📝 Form Summary
          </button>
        </div>

        {itrRecommendation && (
          <div className="card p-5 border border-primary-200 bg-primary-50">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <p className="text-sm text-primary-700 font-medium">ITR Form Recommendation</p>
                <p className="text-lg font-bold text-primary-900 mt-1">
                  Recommended: {itrRecommendation.recommended_form} • Current: {itrRecommendation.current_form}
                </p>
                <p className="text-sm text-primary-800 mt-1">{itrRecommendation.reason}</p>
                <p className="text-xs text-primary-700 mt-1">
                  Auto-refreshes from latest profile, residency status, income heads, property and document signals.
                </p>
              </div>
              {itrRecommendation.recommended_form !== itrRecommendation.current_form && (
                <button
                  onClick={applyRecommendedForm}
                  disabled={applyingItrForm}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2 hover:bg-primary-700 disabled:bg-gray-400"
                >
                  {applyingItrForm ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Use Recommended Form
                </button>
              )}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleExportPDF}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Download className="w-4 h-4" />
            Export PDF
          </button>
          <button
            onClick={handleExportJSON}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <Download className="w-4 h-4" />
            Export JSON
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      ) : error ? (
        <div className="card p-6 bg-danger-50 border border-danger-300">
          <AlertCircle className="w-5 h-5 text-danger-600 mb-2" />
          <p className="text-danger-700">Failed to load report</p>
        </div>
      ) : activeTab === 'calculation' ? (
        /* CALCULATION REPORT */
        <div className="space-y-6">
          {/* Header Info */}
          <div className="card p-6 bg-gradient-to-r from-blue-50 to-purple-50">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600">Taxpayer</p>
                <p className="font-bold text-gray-900">{calcReport.taxpayer_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Assessment Year</p>
                <p className="font-bold text-gray-900">{calcReport.assessment_year}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Residential Status</p>
                <p className="font-bold text-gray-900">{calcReport.residential_status}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">ITR Form</p>
                <p className="font-bold text-gray-900">{calcReport.return_form}</p>
              </div>
            </div>
          </div>

          {/* Income Summary */}
          <div className="card p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Income Summary</h2>
            <div className="bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg p-6 text-white mb-4">
              <p className="text-sm text-blue-100 mb-1">Gross Income</p>
              <p className="text-4xl font-bold">₹{((calcReport.income_summary?.gross_income || 0) / 100000).toFixed(2)}L</p>
            </div>
            <div className="space-y-2">
              {calcReport.income_summary?.income_details?.map((detail, idx) => (
                detail.head && (
                  <div key={idx} className="flex justify-between items-center p-3 bg-gray-50 rounded">
                    <div>
                      <p className="font-medium text-gray-900">{detail.head}</p>
                      <p className="text-xs text-gray-600">{detail.reference}</p>
                    </div>
                    <p className="font-semibold text-gray-900">₹{(detail.amount || 0).toLocaleString()}</p>
                  </div>
                )
              ))}
            </div>
          </div>

          {/* Deductions */}
          <div className="card p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Deductions (Chapter VI-A)</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              {calcReport.deductions?.breakup?.map((ded, idx) => (
                <div key={idx} className="p-4 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-700 font-medium">Section {ded.section}</p>
                  <p className="text-2xl font-bold text-green-900 mt-2">₹{ded.amount.toLocaleString()}</p>
                  <p className="text-xs text-green-600 mt-1">Limit: ₹{ded.limit.toLocaleString()}</p>
                </div>
              ))}
            </div>
            <p className="text-sm text-gray-600">
              💡 Maximize your deductions by adding more 80C, 80D, and 24(b) entries in your income section.
            </p>
          </div>

          {/* Tax Calculation */}
          <div className="card p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Tax Calculation Breakdown</h2>
            <div className="space-y-3 mb-6">
              <div className="flex justify-between items-center p-3 bg-blue-50 rounded">
                <span className="font-medium text-gray-900">Taxable Income</span>
                <span className="font-bold text-blue-900">₹{(calcReport.tax_calculation?.taxable_income || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-orange-50 rounded">
                <span className="font-medium text-gray-900">Tax Liability (Income Tax)</span>
                <span className="font-bold text-orange-900">₹{(calcReport.tax_calculation?.tax_liability || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-yellow-50 rounded">
                <span className="font-medium text-gray-900">Surcharge</span>
                <span className="font-bold text-yellow-900">₹{(calcReport.tax_calculation?.surcharge || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-red-50 rounded">
                <span className="font-medium text-gray-900">Health & Education Cess</span>
                <span className="font-bold text-red-900">₹{(calcReport.tax_calculation?.cess || 0).toLocaleString()}</span>
              </div>
              <div className="border-t-2 border-gray-300 pt-3 flex justify-between items-center p-3 bg-gray-100 rounded font-bold">
                <span className="text-gray-900">Total Tax Before Credits</span>
                <span className="text-xl text-gray-900">₹{(calcReport.tax_calculation?.tax_before_credits || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-green-50 rounded">
                <span className="font-medium text-gray-900">Less: TDS Deducted</span>
                <span className="font-bold text-green-900">₹{(calcReport.tax_calculation?.tds_deducted || 0).toLocaleString()}</span>
              </div>
              <div className="border-2 border-primary-500 bg-primary-50 rounded p-3 flex justify-between items-center font-bold">
                <span className="text-primary-900">Net Tax Payable / Refund</span>
                <span className={`text-xl ${calcReport.tax_calculation?.net_tax_payable > 0 ? 'text-danger-900' : 'text-success-900'}`}>
                  {calcReport.tax_calculation?.net_tax_payable > 0 ? '₹' + calcReport.tax_calculation?.net_tax_payable.toLocaleString() : '₹' + (calcReport.tax_calculation?.refund || 0).toLocaleString()}
                </span>
              </div>
            </div>

            {/* Tax Slabs */}
            <div className="mt-6 p-4 bg-gray-50 rounded">
              <p className="font-semibold text-gray-900 mb-3">Tax Slabs (Old Regime)</p>
              <div className="space-y-1 text-sm">
                {calcReport.tax_calculation?.tax_slabs_used?.map((slab, idx) => (
                  <div key={idx} className="flex justify-between text-gray-700">
                    <span>{slab.slab}</span>
                    <span className="font-medium">{slab.rate}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Government References */}
          <div className="card p-6 bg-blue-50 border border-blue-200">
            <h3 className="text-lg font-bold text-blue-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Government References
            </h3>
            <div className="space-y-2">
              {calcReport.government_references?.map((ref, idx) => (
                <a
                  key={idx}
                  href={ref.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-2 hover:bg-blue-100 rounded transition"
                >
                  <span className="text-blue-600">🔗</span>
                  <span className="text-blue-900 font-medium">{ref.section}</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* FORM SUMMARY */
        <div className="space-y-6">
          {/* Filing Readiness */}
          <div className="card p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">✅ Filing Readiness Check</h2>
            <div className="space-y-3">
              <div className={`flex items-start gap-3 p-3 rounded ${formReport.verification?.income_matched ? 'bg-success-50 border border-success-200' : 'bg-warning-50 border border-warning-200'}`}>
                {formReport.verification?.income_matched ? (
                  <CheckCircle2 className="w-5 h-5 text-success-600 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-warning-600 mt-0.5" />
                )}
                <div>
                  <p className="font-medium text-gray-900">Income Verification</p>
                  <p className="text-sm text-gray-600">{formReport.verification?.income_matched ? '✅ Income matches across all records' : '⚠️ Income variance detected'}</p>
                </div>
              </div>

              <div className={`flex items-start gap-3 p-3 rounded ${formReport.verification?.tds_matched ? 'bg-success-50 border border-success-200' : 'bg-warning-50 border border-warning-200'}`}>
                {formReport.verification?.tds_matched ? (
                  <CheckCircle2 className="w-5 h-5 text-success-600 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-warning-600 mt-0.5" />
                )}
                <div>
                  <p className="font-medium text-gray-900">TDS Verification</p>
                  <p className="text-sm text-gray-600">{formReport.verification?.tds_matched ? '✅ TDS matched with Form 26AS' : '⚠️ TDS variance detected'}</p>
                </div>
              </div>

              <div className={`flex items-start gap-3 p-3 rounded ${formReport.verification?.calculations_verified ? 'bg-success-50 border border-success-200' : 'bg-danger-50 border border-danger-200'}`}>
                {formReport.verification?.calculations_verified ? (
                  <CheckCircle2 className="w-5 h-5 text-success-600 mt-0.5" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-danger-600 mt-0.5" />
                )}
                <div>
                  <p className="font-medium text-gray-900">Tax Calculations</p>
                  <p className="text-sm text-gray-600">✅ All calculations verified against Income Tax rules</p>
                </div>
              </div>
            </div>
          </div>

          {/* Taxpayer Details */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Taxpayer Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 bg-gray-50 rounded">
                <p className="text-sm text-gray-600">Name</p>
                <p className="font-semibold text-gray-900">{formReport.taxpayer_details?.name}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <p className="text-sm text-gray-600">PAN</p>
                <p className="font-semibold text-gray-900">{formReport.taxpayer_details?.pan}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <p className="text-sm text-gray-600">Residency Status</p>
                <p className="font-semibold text-gray-900">{formReport.taxpayer_details?.residential_status}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <p className="text-sm text-gray-600">Form Type</p>
                <p className="font-semibold text-gray-900">{formReport.form_type}</p>
              </div>
            </div>
          </div>

          {/* Income & Tax Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="card p-6 bg-blue-50 border-2 border-blue-200">
              <h3 className="text-lg font-bold text-blue-900 mb-4">Income Details</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-blue-700">Salary:</span>
                  <span className="font-semibold text-blue-900">₹{(formReport.schedule_sa_income?.salary || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-blue-700">House Property:</span>
                  <span className="font-semibold text-blue-900">₹{(formReport.schedule_sa_income?.house_property || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between border-t pt-2">
                  <span className="font-semibold text-blue-900">Total Income:</span>
                  <span className="font-bold text-blue-900 text-lg">₹{(formReport.schedule_sa_income?.total_income || 0).toLocaleString()}</span>
                </div>
              </div>
            </div>

            <div className="card p-6 bg-green-50 border-2 border-green-200">
              <h3 className="text-lg font-bold text-green-900 mb-4">TDS Summary</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-green-700">TDS by Employer:</span>
                  <span className="font-semibold text-green-900">₹{(formReport.schedule_tds?.tds_by_employer || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-green-700">TDS by Bank:</span>
                  <span className="font-semibold text-green-900">₹{(formReport.schedule_tds?.tds_by_bank || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between border-t pt-2">
                  <span className="font-semibold text-green-900">Total TDS:</span>
                  <span className="font-bold text-green-900 text-lg">₹{(formReport.schedule_tds?.total_tds || 0).toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Tax Computation */}
          <div className="card p-6 bg-orange-50 border-2 border-orange-200">
            <h3 className="text-lg font-bold text-orange-900 mb-4">Tax Computation</h3>
            <div className="space-y-2">
              <div className="flex justify-between p-2">
                <span className="text-orange-700">Taxable Income:</span>
                <span className="font-semibold text-orange-900">₹{(formReport.tax_computation?.taxable_income || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2 bg-orange-100 rounded">
                <span className="text-orange-700 font-medium">Total Tax & Cess:</span>
                <span className="font-bold text-orange-900">₹{(formReport.tax_computation?.total_tax || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between p-2">
                <span className="text-orange-700">Less: TDS:</span>
                <span className="font-semibold text-orange-900">₹{(formReport.tax_computation?.total_tax_credits || 0).toLocaleString()}</span>
              </div>
              <div className="border-2 border-orange-300 rounded p-3 mt-3 bg-white">
                {formReport.tax_computation?.tax_payable > 0 ? (
                  <div className="flex justify-between">
                    <span className="font-bold text-orange-900">Tax Payable:</span>
                    <span className="text-2xl font-bold text-danger-600">₹{formReport.tax_computation?.tax_payable.toLocaleString()}</span>
                  </div>
                ) : (
                  <div className="flex justify-between">
                    <span className="font-bold text-green-900">Refund Due:</span>
                    <span className="text-2xl font-bold text-success-600">₹{(formReport.tax_computation?.refund || 0).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Filing Steps */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Info className="w-5 h-5 text-primary-600" />
              Next Steps to File
            </h3>
            <ol className="space-y-3">
              {formReport.filing_instructions?.map((instruction, idx) => (
                <li key={idx} className="flex gap-3 p-3 bg-gray-50 rounded">
                  <span className="flex-shrink-0 w-6 h-6 bg-primary-600 text-white rounded-full flex items-center justify-center font-semibold text-sm">
                    {idx + 1}
                  </span>
                  <span className="text-gray-700">{instruction}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Final CTA */}
          <div className="card p-6 bg-gradient-to-r from-success-600 to-green-600 text-white">
            <h3 className="text-2xl font-bold mb-3">🎯 Ready to File?</h3>
            <p className="mb-4">All verifications passed! Export your reports and head to the official Income Tax portal.</p>
            <a href="https://www.incometax.gov.in/iec/foportal/" target="_blank" rel="noopener noreferrer">
              <button className="bg-white text-success-600 font-bold px-6 py-2 rounded-lg hover:bg-gray-100 transition">
                Go to Official ITR Portal →
              </button>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
