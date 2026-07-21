import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  ListTodo,
  Loader2,
} from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const num = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};
const inr = (value) => `₹${num(value).toLocaleString('en-IN')}`;
const text = (value, fallback = '—') =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;

function ProgressBar({ label, value, color = 'bg-primary-600' }) {
  const safeValue = clamp(num(value), 0, 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <p className="text-sm text-gray-700">{label}</p>
        <p className="text-sm font-semibold text-gray-900">{safeValue}%</p>
      </div>
      <div className="h-2 rounded-full bg-gray-200">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}

function KpiCard({ label, value, hint, valueClass = 'text-primary-600', icon }) {
  const Icon = icon;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-600">{label}</p>
        {Icon ? <Icon className="w-4 h-4 text-gray-400" /> : null}
      </div>
      <p className={`text-3xl font-bold mt-1 ${valueClass}`}>{value}</p>
      {hint ? <p className="text-xs text-gray-500 mt-1">{hint}</p> : null}
    </div>
  );
}

export default function Dashboard() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data: caseData, isLoading } = useSWR(apiUrl(`/api/cases/${caseId}`), fetcher);
  const { data: progressData } = useSWR(apiUrl(`/api/cases/${caseId}/progress`), fetcher);
  const { data: checksData } = useSWR(apiUrl(`/api/cases/${caseId}/review-checks`), fetcher);
  const { data: householdData } = useSWR(apiUrl('/api/household/summary'), fetcher);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const progress = progressData?.progress && typeof progressData.progress === 'object' ? progressData.progress : {};
  const checks = Array.isArray(checksData?.checks) ? checksData.checks : [];
  const caseInfo = caseData?.case && typeof caseData.case === 'object' ? caseData.case : {};

  const severity = checks.reduce(
    (acc, check) => {
      if (check.severity === 'BLOCK') acc.block += 1;
      else if (check.severity === 'WARN') acc.warn += 1;
      else acc.ok += 1;
      return acc;
    },
    { block: 0, warn: 0, ok: 0 }
  );

  const readinessScore = clamp(
    Math.round(num(progress.overall) - severity.block * 8 - severity.warn * 3),
    0,
    100
  );

  const household = householdData?.household_summary && typeof householdData.household_summary === 'object'
    ? householdData.household_summary
    : {};
  const topBlockers = checks.filter((c) => c.severity === 'BLOCK').slice(0, 3);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">
            {text(caseInfo.residential_status)} • AY {text(caseInfo.assessment_year)} • Case {num(caseId)}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-white border border-gray-200 px-3 py-2">
          <BarChart3 className="w-4 h-4 text-primary-600" />
          <span className="text-sm text-gray-700">Tax Readiness</span>
          <span className="text-sm font-bold text-primary-700">{`${num(readinessScore)}%`}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          label="Overall Progress"
          value={`${num(progress.overall)}%`}
          hint="Documents + workflow"
          valueClass="text-primary-600"
          icon={BarChart3}
        />
        <KpiCard
          label="Documents Completion"
          value={`${num(progress.documents)}%`}
          hint="Required docs received/verified"
          valueClass="text-blue-600"
          icon={CheckCircle2}
        />
        <KpiCard
          label="Missing Required"
          value={num(progress.missing_required)}
          hint="Needs immediate action"
          valueClass="text-red-600"
          icon={AlertCircle}
        />
        <KpiCard
          label="Open Tasks"
          value={num(progress.open_tasks)}
          hint="Pending filings workflow"
          valueClass="text-orange-600"
          icon={ListTodo}
        />
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Step-by-step filing journey</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-2 text-sm">
          {[
            ['1. Profile', '/profile'],
            ['2. Residency', '/residency'],
            ['3. Documents', '/document-fetcher'],
            ['4. Income + Credits', '/income'],
            ['5. Reconcile + Review + Export', '/review'],
          ].map(([label, href]) => (
            <a key={label} href={href} className="rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-primary-800 hover:bg-primary-100">
              {label}
            </a>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 bg-white rounded-lg border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Workflow Progress</h2>
          <ProgressBar label="Documents" value={progress.documents} color="bg-blue-600" />
          <ProgressBar label="Tasks" value={progress.tasks} color="bg-orange-500" />
          <ProgressBar label="Overall Filing" value={progress.overall} color="bg-primary-600" />
        </div>

        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Compliance Snapshot</h2>
          <p className="text-xs text-gray-600 mb-3">
            Live checks from your current case data (documents, residency, income, form suitability). Not mock data.
          </p>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-3 py-2">
              <span className="text-sm text-red-800 inline-flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Blockers</span>
              <span className="font-bold text-red-700">{num(severity.block)}</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2">
              <span className="text-sm text-yellow-800 inline-flex items-center gap-2"><AlertCircle className="w-4 h-4" /> Warnings</span>
              <span className="font-bold text-yellow-700">{num(severity.warn)}</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-3 py-2">
              <span className="text-sm text-green-800 inline-flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> OK checks</span>
              <span className="font-bold text-green-700">{num(severity.ok)}</span>
            </div>
          </div>
          {topBlockers.length > 0 ? (
            <div className="mt-4 space-y-2">
              {topBlockers.map((b, idx) => (
                <div key={`${b.area}-${idx}`} className="rounded-lg bg-red-50 border border-red-200 p-2">
                  <p className="text-xs font-semibold text-red-900">{b.area}</p>
                  <p className="text-xs text-red-800">{b.message}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Household Tracking (Combined)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p className="text-xs text-gray-600">Combined Income</p>
            <p className="text-2xl font-bold text-blue-700">{inr(household.total_income)}</p>
          </div>
          <div className="rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-xs text-gray-600">Combined Tax Paid (TDS)</p>
            <p className="text-2xl font-bold text-green-700">{inr(household.total_tds_deducted)}</p>
          </div>
          <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
            <p className="text-xs text-gray-600">Estimated Total Tax</p>
            <p className="text-2xl font-bold text-purple-700">{inr(household.estimated_total_tax)}</p>
          </div>
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
            <p className="text-xs text-gray-600">Estimated Combined Refund</p>
            <p className="text-2xl font-bold text-yellow-700">{inr(household.total_refund)}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Current Issues</h2>
        <div className="space-y-2">
          {checks.length === 0 ? (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="w-5 h-5" />
              <span>No issues found - continue with filing</span>
            </div>
          ) : (
            checks.slice(0, 10).map((check, i) => (
              <div
                key={i}
                className={`flex items-start gap-3 p-3 rounded-lg ${
                  check.severity === 'BLOCK'
                    ? 'bg-red-50 border border-red-200'
                    : check.severity === 'WARN'
                    ? 'bg-yellow-50 border border-yellow-200'
                    : 'bg-green-50 border border-green-200'
                }`}
              >
                <AlertCircle
                  className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                    check.severity === 'BLOCK'
                      ? 'text-red-600'
                      : check.severity === 'WARN'
                      ? 'text-yellow-600'
                      : 'text-green-600'
                  }`}
                />
                <div>
                  <p className="font-semibold text-gray-900">{check.area}</p>
                  <p className="text-sm text-gray-700">{check.message}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Priority Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/documents" className="flex items-center gap-3 p-4 rounded-lg border border-primary-200 bg-primary-50 hover:bg-primary-100 transition">
            <AlertCircle className="w-5 h-5 text-primary-600" />
            <div>
              <p className="font-semibold text-gray-900">Upload Missing Documents</p>
              <p className="text-sm text-gray-600">{num(progress.missing_required)} pending required docs</p>
            </div>
          </a>
          <a href="/residency" className="flex items-center gap-3 p-4 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 transition">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <div>
              <p className="font-semibold text-gray-900">Resolve Residency Blockers</p>
              <p className="text-sm text-gray-600">Complete day-count worksheet and recommendation</p>
            </div>
          </a>
          <a href="/review" className="flex items-center gap-3 p-4 rounded-lg border border-purple-200 bg-purple-50 hover:bg-purple-100 transition">
            <CheckCircle2 className="w-5 h-5 text-purple-600" />
            <div>
              <p className="font-semibold text-gray-900">Close Review Exceptions</p>
              <p className="text-sm text-gray-600">{severity.block + severity.warn} open checks to resolve</p>
            </div>
          </a>
        </div>
      </div>
    </div>
  );
}
