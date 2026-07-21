import { useEffect, useState } from 'react';
import { Clock3, Loader2, AlertCircle, Save, Sparkles, CheckCircle2 } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const DEFAULT_FORM = {
  days_in_india_current_fy: '',
  days_in_india_prior_4y: '',
  days_in_india_prior_7y: '',
  nonresident_years_prior_10y: '',
  date_returned_to_india: '',
  foreign_income_received_in_india: false,
  business_controlled_from_india: false,
  conclusion: 'NRI',
  reviewed_by: '',
  notes: '',
};

export default function Residency() {
  const { selectedCaseId, selectedMember } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, error, isLoading, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/residency`), fetcher);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [assessment, setAssessment] = useState(null);

  useEffect(() => {
    if (data?.residency) {
      setForm({
        ...DEFAULT_FORM,
        ...data.residency,
        days_in_india_current_fy: data.residency.days_in_india_current_fy ?? '',
        days_in_india_prior_4y: data.residency.days_in_india_prior_4y ?? '',
        days_in_india_prior_7y: data.residency.days_in_india_prior_7y ?? '',
        nonresident_years_prior_10y: data.residency.nonresident_years_prior_10y ?? '',
      });
    } else {
      setForm(DEFAULT_FORM);
    }
    setAssessment(null);
  }, [data, caseId]);

  const save = async () => {
    setSaving(true);
    try {
      await apiCall('POST', `/api/cases/${caseId}/residency`, {
        ...form,
        days_in_india_current_fy: form.days_in_india_current_fy === '' ? null : Number(form.days_in_india_current_fy),
        days_in_india_prior_4y: form.days_in_india_prior_4y === '' ? null : Number(form.days_in_india_prior_4y),
        days_in_india_prior_7y: form.days_in_india_prior_7y === '' ? null : Number(form.days_in_india_prior_7y),
        nonresident_years_prior_10y: form.nonresident_years_prior_10y === '' ? null : Number(form.nonresident_years_prior_10y),
      });
      await mutate();
    } finally {
      setSaving(false);
    }
  };

  const assess = async () => {
    const result = await apiCall('POST', '/api/residency/assess', {
      days_in_india_current_fy: Number(form.days_in_india_current_fy || 0),
      days_in_india_prior_4y: Number(form.days_in_india_prior_4y || 0),
      days_in_india_prior_7y: Number(form.days_in_india_prior_7y || 0),
      nonresident_years_prior_10y: Number(form.nonresident_years_prior_10y || 0),
      indian_citizen_or_pio: (selectedMember?.citizenship || 'Indian') !== 'Foreign',
      visiting_india: !!form.date_returned_to_india,
      indian_income_excluding_foreign: 0,
      not_liable_to_tax_elsewhere: false,
    });
    setAssessment(result?.assessment || null);
  };

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  }

  if (error) {
    return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading residency</span></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Clock3 className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Residency Worksheet</h1>
          <p className="text-gray-600">Case {caseId} • NRI / RNOR / ROR day-count review</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Current Status</p><p className="text-2xl font-bold text-primary-600">{data?.case_status || 'Unknown'}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Current FY Days</p><p className="text-2xl font-bold text-blue-600">{form.days_in_india_current_fy || 0}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Prior 4Y Days</p><p className="text-2xl font-bold text-green-600">{form.days_in_india_prior_4y || 0}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Conclusion</p><p className="text-2xl font-bold text-purple-600">{form.conclusion}</p></div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
        This worksheet directly drives compliance blockers and ITR form recommendation. Enter day counts first, then click
        <strong> Recommend Status</strong>, then save the final conclusion.
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            ['days_in_india_current_fy', 'Days in India - Current FY'],
            ['days_in_india_prior_4y', 'Days in India - Prior 4 FYs'],
            ['days_in_india_prior_7y', 'Days in India - Prior 7 FYs'],
            ['nonresident_years_prior_10y', 'Nonresident Years in Prior 10 FYs'],
          ].map(([key, label]) => (
            <label key={key} className="block">
              <span className="block text-sm font-medium text-gray-700">{label}</span>
              <input
                type="number"
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
              />
            </label>
          ))}
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Date Returned to India</span>
            <input
              type="date"
              value={form.date_returned_to_india || ''}
              onChange={(e) => setForm({ ...form, date_returned_to_india: e.target.value })}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Reviewed By</span>
            <input
              type="text"
              value={form.reviewed_by || ''}
              onChange={(e) => setForm({ ...form, reviewed_by: e.target.value })}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={!!form.foreign_income_received_in_india} onChange={(e) => setForm({ ...form, foreign_income_received_in_india: e.target.checked })} />
            <span>Foreign income received in India</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={!!form.business_controlled_from_india} onChange={(e) => setForm({ ...form, business_controlled_from_india: e.target.checked })} />
            <span>Business controlled from India</span>
          </label>
        </div>

        <label className="block">
          <span className="block text-sm font-medium text-gray-700">Conclusion</span>
          <select value={form.conclusion} onChange={(e) => setForm({ ...form, conclusion: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
            <option value="NRI">NRI</option>
            <option value="RNOR">RNOR</option>
            <option value="ROR">ROR</option>
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-gray-700">Notes</span>
          <textarea
            value={form.notes || ''}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-28"
          />
        </label>

        <div className="flex gap-3">
          <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white">
            <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save Residency'}
          </button>
          <button onClick={assess} className="inline-flex items-center gap-2 rounded-lg bg-gray-200 px-4 py-2 text-gray-900">
            <Sparkles className="w-4 h-4" /> Recommend Status
          </button>
        </div>
      </div>

      {assessment && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Recommendation</h2>
          <div className="space-y-2 text-sm text-gray-700">
            <p><strong>Recommended:</strong> {assessment.recommended_status}</p>
            <p><strong>Basis:</strong> {assessment.status_basis}</p>
            <p><strong>Threshold logic:</strong> {assessment.threshold_reason}</p>
            {(assessment.checks || []).map((item, idx) => (
              <div key={idx} className="flex items-start gap-2"><CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" /><span>{item.rule}: {item.passed ? 'Pass' : 'No'} ({item.detail})</span></div>
            ))}
            <p><strong>References:</strong> {(assessment.government_sources || []).join(' | ')}</p>
            <p><strong>Disclaimer:</strong> {assessment.disclaimer}</p>
          </div>
        </div>
      )}
    </div>
  );
}
