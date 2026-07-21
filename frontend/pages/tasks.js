import { useState } from 'react';
import { ListTodo, Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import useSWR from 'swr';
import { apiCall, fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

export default function Tasks() {
  const { selectedCaseId } = useCaseContext();
  const caseId = selectedCaseId || 1;
  const { data, error, isLoading, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/tasks`), fetcher);
  const [savingId, setSavingId] = useState(null);
  const [resetting, setResetting] = useState(false);

  const updateStatus = async (taskId, status) => {
    setSavingId(taskId);
    try {
      await apiCall('PUT', `/api/cases/${caseId}/tasks/${taskId}`, { status });
      await mutate();
    } finally {
      setSavingId(null);
    }
  };

  const resetAll = async () => {
    setResetting(true);
    try {
      await apiCall('POST', `/api/cases/${caseId}/tasks/reset`);
      await mutate();
    } finally {
      setResetting(false);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (error) return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading tasks</span></div>;

  const tasks = data?.tasks || [];
  const counts = tasks.reduce((acc, task) => {
    acc[task.status] = (acc[task.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <ListTodo className="w-8 h-8 text-primary-600" />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Tasks</h1>
          <p className="text-gray-600">Statuses are manual. Suggested next status is shown from profile, residency, documents and filing signals.</p>
        </div>
      </div>
      <div className="bg-blue-50 border border-blue-200 text-blue-900 rounded-lg p-3 text-sm flex items-center justify-between gap-3">
        <span>If you see old completed tasks from earlier runs, reset this case to start clean.</span>
        <button
          onClick={resetAll}
          disabled={resetting}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 text-white px-3 py-2 hover:bg-blue-700 disabled:bg-blue-300"
        >
          <RotateCcw className="w-4 h-4" />
          {resetting ? 'Resetting...' : 'Reset all to Not started'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {['Not started', 'In progress', 'Complete', 'Blocked'].map((label) => (
          <div key={label} className="bg-white rounded-lg border border-gray-200 p-4">
            <p className="text-sm text-gray-600">{label}</p>
            <p className="text-2xl font-bold text-primary-600">{counts[label] || 0}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
        {tasks.length === 0 ? (
          <p className="text-sm text-gray-600">No tasks seeded yet.</p>
        ) : tasks.map((task) => (
          <div key={task.id} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <p className="font-semibold text-gray-900">{task.title}</p>
                <p className="text-sm text-gray-600">{task.phase} • {task.code}</p>
              </div>
              <div className="flex items-center gap-2">
                {task.blocking && <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-semibold text-red-700">Blocking</span>}
                {task.suggested_status && task.suggested_status !== task.status && (
                  <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                    Suggested: {task.suggested_status}
                  </span>
                )}
                <select
                  value={task.status}
                  onChange={(e) => updateStatus(task.id, e.target.value)}
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2"
                >
                  <option>Not started</option>
                  <option>In progress</option>
                  <option>Complete</option>
                  <option>Blocked</option>
                </select>
                {savingId === task.id && <Loader2 className="w-4 h-4 animate-spin text-primary-600" />}
              </div>
            </div>
            {task.notes && <p className="mt-2 text-sm text-gray-700">{task.notes}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
