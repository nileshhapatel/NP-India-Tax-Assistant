import { useEffect, useMemo, useState } from 'react';
import {
  Clock3, Loader2, AlertCircle, Save, Sparkles, CheckCircle2, Plane, Plus, Trash2, Calculator, Pencil, Check, X,
} from 'lucide-react';
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
  fy_start_location: 'outside_india',
  reviewed_by: '',
  notes: '',
};

const DEFAULT_TRIP = {
  departure_date: '',
  arrival_date: '',
  from_country: 'India',
  to_country: 'Outside India',
  trip_purpose: '',
  notes: '',
};

export default function Residency() {
  const { selectedCaseId, selectedMember } = useCaseContext();
  const caseId = selectedCaseId || 1;

  const { data, error, isLoading, mutate } = useSWR(apiUrl(`/api/cases/${caseId}/residency`), fetcher);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [tripForm, setTripForm] = useState(DEFAULT_TRIP);
  const [tripBusy, setTripBusy] = useState(false);
  const [editingTripId, setEditingTripId] = useState(null);
  const [editingTripForm, setEditingTripForm] = useState(DEFAULT_TRIP);
  const [recomputing, setRecomputing] = useState(false);
  const [message, setMessage] = useState('');

  const travelHistory = data?.travel_history || [];
  const computed = data?.computed_days_from_travel || null;

  useEffect(() => {
    if (data?.residency) {
      setForm({
        ...DEFAULT_FORM,
        ...data.residency,
        fy_start_location: data?.residency_settings?.fy_start_location || DEFAULT_FORM.fy_start_location,
        days_in_india_current_fy: data.residency.days_in_india_current_fy ?? '',
        days_in_india_prior_4y: data.residency.days_in_india_prior_4y ?? '',
        days_in_india_prior_7y: data.residency.days_in_india_prior_7y ?? '',
        nonresident_years_prior_10y: data.residency.nonresident_years_prior_10y ?? '',
      });
    } else {
      setForm({ ...DEFAULT_FORM, fy_start_location: data?.residency_settings?.fy_start_location || DEFAULT_FORM.fy_start_location });
    }
    setAssessment(null);
  }, [data, caseId]);

  const selectedTaxpayerCitizen = useMemo(
    () => (selectedMember?.citizenship || 'Indian').trim().toLowerCase(),
    [selectedMember],
  );

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/residency`, {
        ...form,
        fy_start_location: form.fy_start_location || 'outside_india',
        days_in_india_current_fy: form.days_in_india_current_fy === '' ? null : Number(form.days_in_india_current_fy),
        days_in_india_prior_4y: form.days_in_india_prior_4y === '' ? null : Number(form.days_in_india_prior_4y),
        days_in_india_prior_7y: form.days_in_india_prior_7y === '' ? null : Number(form.days_in_india_prior_7y),
        nonresident_years_prior_10y: form.nonresident_years_prior_10y === '' ? null : Number(form.nonresident_years_prior_10y),
      });
      setMessage('Residency worksheet saved.');
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
      indian_citizen_or_pio: selectedTaxpayerCitizen !== 'foreign',
      visiting_india: !!form.date_returned_to_india,
      indian_income_excluding_foreign: 0,
      not_liable_to_tax_elsewhere: false,
    });
    setAssessment(result?.assessment || null);
  };

  const addTrip = async () => {
    if (!tripForm.departure_date || !tripForm.arrival_date) {
      setMessage('Departure and arrival dates are required.');
      return;
    }
    setTripBusy(true);
    setMessage('');
    try {
      await apiCall('POST', `/api/cases/${caseId}/travel-history`, tripForm);
      setTripForm(DEFAULT_TRIP);
      await mutate();
      setMessage('Travel entry added.');
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setTripBusy(false);
    }
  };

  const removeTrip = async (tripId) => {
    setTripBusy(true);
    setMessage('');
    try {
      await apiCall('DELETE', `/api/cases/${caseId}/travel-history/${tripId}`);
      await mutate();
      setMessage('Travel entry removed.');
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setTripBusy(false);
    }
  };

  const startEditTrip = (trip) => {
    setEditingTripId(trip.id);
    setEditingTripForm({
      departure_date: trip.departure_date || '',
      arrival_date: trip.arrival_date || '',
      from_country: trip.from_country || 'India',
      to_country: trip.to_country || 'Outside India',
      trip_purpose: trip.trip_purpose || '',
      notes: trip.notes || '',
    });
  };

  const cancelEditTrip = () => {
    setEditingTripId(null);
    setEditingTripForm(DEFAULT_TRIP);
  };

  const saveEditTrip = async () => {
    if (!editingTripId) return;
    if (!editingTripForm.departure_date || !editingTripForm.arrival_date) {
      setMessage('Departure and arrival dates are required.');
      return;
    }
    setTripBusy(true);
    setMessage('');
    try {
      await apiCall('PUT', `/api/cases/${caseId}/travel-history/${editingTripId}`, editingTripForm);
      setEditingTripId(null);
      setEditingTripForm(DEFAULT_TRIP);
      await mutate();
      setMessage('Travel entry updated.');
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setTripBusy(false);
    }
  };

  const recomputeFromTravel = async () => {
    setRecomputing(true);
    setMessage('');
    try {
      const res = await apiCall('POST', `/api/cases/${caseId}/residency/recompute-from-travel`, {
        fy_start_location: form.fy_start_location || 'outside_india',
        nonresident_years_prior_10y: form.nonresident_years_prior_10y === '' ? 0 : Number(form.nonresident_years_prior_10y),
        date_returned_to_india: form.date_returned_to_india || null,
      });
      if (res?.residency) {
        setForm((prev) => ({
          ...prev,
          ...res.residency,
          fy_start_location: res?.residency_settings?.fy_start_location || prev.fy_start_location,
          days_in_india_current_fy: res.residency.days_in_india_current_fy ?? '',
          days_in_india_prior_4y: res.residency.days_in_india_prior_4y ?? '',
          days_in_india_prior_7y: res.residency.days_in_india_prior_7y ?? '',
          nonresident_years_prior_10y: res.residency.nonresident_years_prior_10y ?? '',
        }));
      }
      setAssessment(res?.assessment || null);
      await mutate();
      setMessage('Day counts auto-calculated from travel history.');
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setRecomputing(false);
    }
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
          <p className="text-gray-600">Case {caseId} • Travel history driven NRI / RNOR / ROR calculation</p>
        </div>
      </div>

      {message ? (
        <div className={`rounded-lg border px-4 py-3 text-sm ${message.startsWith('Error') ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}>
          {message}
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Trips Logged</p><p className="text-2xl font-bold text-primary-600">{travelHistory.length}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Current FY Days</p><p className="text-2xl font-bold text-blue-600">{(computed?.days_in_india_current_fy ?? form.days_in_india_current_fy) || 0}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Prior 4 FY Days</p><p className="text-2xl font-bold text-green-600">{(computed?.days_in_india_prior_4y ?? form.days_in_india_prior_4y) || 0}</p></div>
        <div className="bg-white rounded-lg border border-gray-200 p-4"><p className="text-sm text-gray-600">Conclusion</p><p className="text-2xl font-bold text-purple-600">{form.conclusion || '—'}</p></div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-900">
        Set your <strong>location at FY start</strong> first (India or Outside India), then add travel legs.
        If you lived in US and only visited India twice, set FY start as <strong>Outside India</strong> and enter only the visit arrival/departure legs.
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2"><Plane className="w-5 h-5 text-primary-600" /> Travel History</h2>
          <button onClick={recomputeFromTravel} disabled={recomputing} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white disabled:bg-gray-400">
            {recomputing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
            Recalculate Days from Travel
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label className="block">
            <span className="block text-sm font-medium text-gray-700">Location at FY start (1-Apr)</span>
            <select
              value={form.fy_start_location}
              onChange={(e) => setForm({ ...form, fy_start_location: e.target.value })}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
            >
              <option value="outside_india">Outside India (e.g., US resident visiting India)</option>
              <option value="india">In India (India resident travelling abroad)</option>
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <label className="block md:col-span-1">
            <span className="block text-sm font-medium text-gray-700">Departure</span>
            <input type="date" value={tripForm.departure_date} onChange={(e) => setTripForm({ ...tripForm, departure_date: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="block md:col-span-1">
            <span className="block text-sm font-medium text-gray-700">Arrival</span>
            <input type="date" value={tripForm.arrival_date} onChange={(e) => setTripForm({ ...tripForm, arrival_date: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="block md:col-span-1">
            <span className="block text-sm font-medium text-gray-700">From</span>
            <input type="text" value={tripForm.from_country} onChange={(e) => setTripForm({ ...tripForm, from_country: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="block md:col-span-1">
            <span className="block text-sm font-medium text-gray-700">To</span>
            <input type="text" value={tripForm.to_country} onChange={(e) => setTripForm({ ...tripForm, to_country: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <label className="block md:col-span-1">
            <span className="block text-sm font-medium text-gray-700">Purpose</span>
            <input type="text" value={tripForm.trip_purpose} onChange={(e) => setTripForm({ ...tripForm, trip_purpose: e.target.value })} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <div className="md:col-span-1 flex items-end">
            <button onClick={addTrip} disabled={tripBusy} className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-white w-full justify-center disabled:bg-gray-400">
              {tripBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Add Trip
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">Departure</th>
                <th className="text-left px-3 py-2">Arrival</th>
                <th className="text-left px-3 py-2">From</th>
                <th className="text-left px-3 py-2">To</th>
                <th className="text-left px-3 py-2">Purpose</th>
                <th className="text-left px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {travelHistory.length === 0 ? (
                <tr><td colSpan={6} className="px-3 py-3 text-gray-500">No trips added yet.</td></tr>
              ) : travelHistory.map((trip) => {
                const isEditing = editingTripId === trip.id;
                return (
                  <tr key={trip.id} className="border-t border-gray-100">
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <input type="date" value={editingTripForm.departure_date} onChange={(e) => setEditingTripForm({ ...editingTripForm, departure_date: e.target.value })} className="w-full rounded border border-gray-300 px-2 py-1" />
                      ) : trip.departure_date}
                    </td>
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <input type="date" value={editingTripForm.arrival_date} onChange={(e) => setEditingTripForm({ ...editingTripForm, arrival_date: e.target.value })} className="w-full rounded border border-gray-300 px-2 py-1" />
                      ) : trip.arrival_date}
                    </td>
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <input type="text" value={editingTripForm.from_country} onChange={(e) => setEditingTripForm({ ...editingTripForm, from_country: e.target.value })} className="w-full rounded border border-gray-300 px-2 py-1" />
                      ) : (trip.from_country || 'India')}
                    </td>
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <input type="text" value={editingTripForm.to_country} onChange={(e) => setEditingTripForm({ ...editingTripForm, to_country: e.target.value })} className="w-full rounded border border-gray-300 px-2 py-1" />
                      ) : (trip.to_country || 'Outside India')}
                    </td>
                    <td className="px-3 py-2">
                      {isEditing ? (
                        <input type="text" value={editingTripForm.trip_purpose} onChange={(e) => setEditingTripForm({ ...editingTripForm, trip_purpose: e.target.value })} className="w-full rounded border border-gray-300 px-2 py-1" />
                      ) : (trip.trip_purpose || '—')}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        {isEditing ? (
                          <>
                            <button onClick={saveEditTrip} disabled={tripBusy} className="inline-flex items-center gap-1 rounded border border-green-200 bg-green-50 px-2 py-1 text-green-700">
                              <Check className="w-3 h-3" /> Update
                            </button>
                            <button onClick={cancelEditTrip} disabled={tripBusy} className="inline-flex items-center gap-1 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-gray-700">
                              <X className="w-3 h-3" /> Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button onClick={() => startEditTrip(trip)} disabled={tripBusy || editingTripId !== null} className="inline-flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-2 py-1 text-blue-700 disabled:bg-gray-100 disabled:text-gray-400">
                              <Pencil className="w-3 h-3" /> Edit
                            </button>
                            <button onClick={() => removeTrip(trip.id)} disabled={tripBusy || editingTripId !== null} className="inline-flex items-center gap-1 rounded border border-red-200 bg-red-50 px-2 py-1 text-red-700 disabled:bg-gray-100 disabled:text-gray-400">
                              <Trash2 className="w-3 h-3" /> Remove
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {computed?.yearly_breakdown?.length ? (
          <div className="rounded-lg border border-gray-200 p-3">
            <p className="text-sm font-medium text-gray-800 mb-2">Year-wise day count (derived from travel)</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
              {computed.yearly_breakdown.slice(0, 7).map((item) => (
                <div key={item.financial_year} className="rounded border border-gray-100 bg-gray-50 px-3 py-2">
                  <p className="font-medium">{item.financial_year}</p>
                  <p>In India: <strong>{item.days_in_india}</strong> days • Outside: <strong>{item.days_outside_india}</strong> days</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Residency Declaration & Context</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            ['days_in_india_current_fy', 'Days in India - Current FY (auto from travel)'],
            ['days_in_india_prior_4y', 'Days in India - Prior 4 FYs (auto from travel)'],
            ['days_in_india_prior_7y', 'Days in India - Prior 7 FYs (auto from travel)'],
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
          <span className="block text-sm font-medium text-gray-700">Final Conclusion</span>
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
          <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white disabled:bg-gray-400">
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
