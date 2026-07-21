import { useState } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { useCaseContext } from '../lib/case-context';
import useSWR from 'swr';
import { fetcher } from '../lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const PRESETS = {
  tax_savings: {
    endpoint: '/api/phase3/optimize/tax-savings',
    payload: {
      total_income: 1200000,
      current_deductions: 150000,
      tax_paid: 110000,
      residency_status: 'NRI',
      current_regime: 'old',
      age: 35,
      has_home_loan: false,
      has_dependents: false,
      num_dependents: 0,
      investment_capacity: 0,
      existing_insurance: [],
      life_events: [],
      filing_deadline_days_remaining: 30,
      risk_profile: 'moderate',
    },
  },
  compliance: {
    endpoint: '/api/phase3/validate/compliance',
    payload: {
      total_income: 1200000,
      residency_status: 'NRI',
      deductions: { '80C': 100000, '80D': 20000 },
      tds_claimed: 110000,
      has_income_from_multiple_sources: true,
      documents_uploaded: ['AIS', '26AS'],
      ais_received: true,
      form_26as_received: true,
      assessment_year: 2027,
    },
  },
  reconciliation: {
    endpoint: '/api/phase3/reconcile/three-way',
    payload: { source_statements: [], ais_entries: [], itr_entries: [] },
  },
  lifecycle: {
    endpoint: '/api/phase3/track/lifecycle-event',
    payload: {
      event_type: 'job_change',
      category: 'employment',
      date_occurred: '2026-01-10',
      description: 'Changed job in FY',
      affected_person: 'self',
      metadata: {},
    },
  },
};

export default function AISpecialists() {
  const { selectedCaseId } = useCaseContext();
  const [selected, setSelected] = useState('tax_savings');
  const [payloadText, setPayloadText] = useState(JSON.stringify(PRESETS.tax_savings.payload, null, 2));
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const caseId = selectedCaseId || 1;
  const { data: caseData } = useSWR(apiUrl(`/api/cases/${caseId}`), fetcher);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const endpoint = PRESETS[selected].endpoint;
      const payload = JSON.parse(payloadText);
      const res = await fetch(apiUrl(endpoint), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const hydrateFromCase = () => {
    const c = caseData?.case || {};
    const base = PRESETS[selected]?.payload || {};
    const next = {
      ...base,
      residency_status: c.residential_status || base.residency_status,
      current_regime: (c.tax_regime || base.current_regime || 'old').toLowerCase(),
    };
    setPayloadText(JSON.stringify(next, null, 2));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Bot className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Specialists Panel</h1>
          <p className="text-gray-600">Explicit specialist invocation and response inspection for case {caseId}.</p>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <label className="block">
          <span className="block text-sm font-medium text-gray-700">Specialist</span>
          <select
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setPayloadText(JSON.stringify(PRESETS[e.target.value].payload, null, 2));
            }}
          >
            <option value="tax_savings">Tax Savings Optimizer</option>
            <option value="compliance">Compliance Validator</option>
            <option value="reconciliation">Reconciliation Expert</option>
            <option value="lifecycle">Lifecycle Tracker</option>
          </select>
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700">Payload (JSON)</span>
          <textarea
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-60 font-mono text-sm"
            value={payloadText}
            onChange={(e) => setPayloadText(e.target.value)}
          />
        </label>
        <button onClick={hydrateFromCase} className="inline-flex items-center gap-2 rounded-lg bg-gray-100 border border-gray-300 text-gray-800 px-3 py-2 text-sm hover:bg-gray-200">
          Load selected case context into payload
        </button>
        <button
          onClick={run}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          Run Specialist
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Response</h2>
        <pre className="text-xs bg-gray-50 rounded p-3 overflow-auto">{JSON.stringify(result, null, 2)}</pre>
      </div>
    </div>
  );
}
