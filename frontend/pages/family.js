import { useState } from 'react';
import { Users, Plus, Pencil, Trash2, Loader2, AlertCircle, CheckCircle2, XCircle, Info, ChevronDown, ChevronRight, RefreshCw, Search } from 'lucide-react';
import useSWR from 'swr';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const RELATIONSHIPS = ['Daughter', 'Son', 'Spouse', 'Father', 'Mother', 'Father-in-law', 'Mother-in-law', 'Brother', 'Sister', 'Other'];
const RESIDENTIAL_STATUSES = ['Indian Resident', 'NRI', 'RNOR', 'OCI Card Holder', 'PIO', 'Foreign National', 'Other'];
const CITIZENSHIPS = ['India', 'USA', 'UK', 'Canada', 'Australia', 'UAE', 'Singapore', 'Germany', 'Other'];

const DEFAULT_FORM = {
  name: '', relationship: 'Daughter', date_of_birth: '', citizenship: 'USA',
  residential_status: 'OCI Card Holder', oci_card_last4: '', pan_last4: '',
  living_in_india: true, currently_studying: true, institution_name: '',
  course_details: '', currently_working: false, employer_country: '',
  has_india_income: false, india_income_notes: '', notes: '',
};

const CATEGORY_COLORS = {
  'Savings / Girl Child': 'pink',
  'Girl Child / Welfare': 'pink',
  'Scholarship / Education': 'purple',
  'Education / Admission': 'blue',
  'Private Scholarship': 'indigo',
  'OCI Rights': 'teal',
  'Banking': 'cyan',
  'Tax Benefit': 'green',
  'Health Insurance': 'orange',
  'State Scholarship': 'violet',
  'State / Girl Child': 'rose',
};

function catColor(cat) {
  const c = CATEGORY_COLORS[cat] || 'gray';
  return {
    badge: `bg-${c}-100 text-${c}-700`,
    border: `border-${c}-200`,
    bg: `bg-${c}-50`,
  };
}

function SchemeCard({ scheme, eligible }) {
  return (
    <div className={`rounded-lg border p-4 space-y-2 ${eligible ? 'border-green-200 bg-green-50' : 'border-red-100 bg-red-50 opacity-75'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {eligible ? <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0 mt-0.5" /> : <XCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />}
          <p className={`text-sm font-semibold ${eligible ? 'text-green-900' : 'text-red-800'}`}>{scheme.name}</p>
        </div>
        <span className={`text-xs rounded-full px-2 py-0.5 shrink-0 ${eligible ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-700'}`}>
          {scheme.category}
        </span>
      </div>
      <p className={`text-xs ${eligible ? 'text-green-800' : 'text-red-700'}`}>{scheme.description}</p>
      {eligible && (
        <>
          <p className="text-xs text-green-900"><strong>Benefit:</strong> {scheme.benefit}</p>
          <p className="text-xs text-green-700"><strong>How to apply:</strong> {scheme.how_to_apply}</p>
          <p className="text-xs text-gray-500">Authority: {scheme.authority}</p>
        </>
      )}
      {!eligible && scheme.reasons?.length > 0 && (
        <ul className="space-y-0.5">
          {scheme.reasons.map((r, i) => <li key={i} className="text-xs text-red-700 flex items-start gap-1"><span className="shrink-0">•</span>{r}</li>)}
        </ul>
      )}
    </div>
  );
}

function EngineResultPanel({ result, taxNotes, memberName }) {
  const [showIneligible, setShowIneligible] = useState(false);
  const [showPartial, setShowPartial] = useState(false);
  if (!result) return null;
  const { eligible, ineligible, partial, summary, profile_used } = result;

  return (
    <div className="space-y-4">
      {/* Summary tiles */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-center">
          <p className="text-2xl font-bold text-green-700">{summary.eligible_count}</p>
          <p className="text-xs text-green-600">Eligible schemes</p>
        </div>
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-center">
          <p className="text-2xl font-bold text-red-600">{summary.ineligible_count}</p>
          <p className="text-xs text-red-600">Not eligible</p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-center">
          <p className="text-2xl font-bold text-amber-600">{summary.needs_info_count}</p>
          <p className="text-xs text-amber-600">Need more info</p>
        </div>
      </div>

      <p className="text-xs text-gray-500">
        Evaluated against {summary.total_schemes_checked} schemes
        {profile_used?.age != null ? ` · Age: ${profile_used.age}` : ' · Age not provided'}
        {profile_used?.is_oci ? ' · OCI card holder' : ''}
        {profile_used?.is_indian_citizen ? ' · Indian citizen' : ' · Non-citizen'}
      </p>

      {/* Eligible */}
      {eligible.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-green-800 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" /> Eligible ({eligible.length})
          </h3>
          {eligible.map(s => <SchemeCard key={s.id} scheme={s} eligible={true} />)}
        </div>
      )}

      {/* Needs info */}
      {partial.length > 0 && (
        <div className="space-y-2">
          <button onClick={() => setShowPartial(!showPartial)} className="flex items-center gap-2 text-sm font-medium text-amber-700">
            {showPartial ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            Needs more info ({partial.length}) — add date of birth to check
          </button>
          {showPartial && partial.map(s => (
            <div key={s.id} className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-800">{s.name}</p>
              {s.reasons?.map((r, i) => <p key={i} className="text-xs text-amber-700">⚠ {r}</p>)}
            </div>
          ))}
        </div>
      )}

      {/* Tax notes */}
      {taxNotes?.length > 0 && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <p className="text-sm font-semibold text-blue-800 mb-2">⚖️ Tax Relevance for your ITR</p>
          {taxNotes.map((n, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-blue-900 mb-1.5">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />{n}
            </div>
          ))}
        </div>
      )}

      {/* Ineligible (collapsed) */}
      <div>
        <button onClick={() => setShowIneligible(!showIneligible)} className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700">
          {showIneligible ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Show not-eligible schemes ({ineligible.length}) — with reasons
        </button>
        {showIneligible && (
          <div className="mt-3 space-y-2">
            {ineligible.map(s => <SchemeCard key={s.id} scheme={s} eligible={false} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function MemberCard({ member, onEdit, onDelete, onRefresh, schemeResult, checking }) {
  const [expanded, setExpanded] = useState(false);
  const isOCI = (member.residential_status || '').toLowerCase().includes('oci');

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between gap-3 p-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-lg">
            {member.name?.[0] || '?'}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{member.name}</h3>
            <p className="text-sm text-gray-500">{member.relationship} · {member.citizenship} · {member.residential_status}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {member.living_in_india && <span className="text-xs bg-blue-100 text-blue-700 rounded-full px-2 py-0.5">Living in India</span>}
          {member.currently_studying && <span className="text-xs bg-purple-100 text-purple-700 rounded-full px-2 py-0.5">Studying</span>}
          {isOCI && <span className="text-xs bg-amber-100 text-amber-700 rounded-full px-2 py-0.5 font-medium">OCI</span>}
          <button onClick={() => { onRefresh(member.id); setExpanded(true); }}
            disabled={checking} title="Find eligible schemes"
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary-600 text-white text-xs hover:bg-primary-700 disabled:bg-gray-400">
            {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />} Find Schemes
          </button>
          <button onClick={() => onEdit(member)} className="p-1.5 rounded hover:bg-gray-100 text-gray-500"><Pencil className="w-4 h-4" /></button>
          <button onClick={() => onDelete(member.id)} className="p-1.5 rounded hover:bg-red-50 text-red-500"><Trash2 className="w-4 h-4" /></button>
          <button onClick={() => setExpanded(!expanded)} className="p-1.5 rounded hover:bg-gray-100 text-gray-500">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 p-5 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div><p className="text-xs text-gray-500">Date of Birth</p><p className="font-medium">{member.date_of_birth || '—'}</p></div>
            <div><p className="text-xs text-gray-500">OCI Card (last 4)</p><p className="font-medium">{member.oci_card_last4 ? `••••${member.oci_card_last4}` : '—'}</p></div>
            <div><p className="text-xs text-gray-500">PAN (last 4)</p><p className="font-medium">{member.pan_last4 ? `••••${member.pan_last4}` : '—'}</p></div>
            <div><p className="text-xs text-gray-500">India Income</p><p className="font-medium">{member.has_india_income ? 'Yes' : 'No'}</p></div>
          </div>

          {(member.institution_name || member.course_details) && (
            <div className="rounded-lg bg-purple-50 border border-purple-200 p-3 text-sm">
              <p className="text-xs font-semibold text-purple-800 mb-1">📚 Education</p>
              <p className="text-purple-900">{member.institution_name}{member.course_details ? ` — ${member.course_details}` : ''}</p>
            </div>
          )}

          {/* Engine result */}
          {schemeResult ? (
            <div>
              <p className="text-sm font-semibold text-gray-800 mb-3">🔍 Scheme Eligibility Results — {member.name}</p>
              <EngineResultPanel result={schemeResult.engine_result} taxNotes={schemeResult.tax_notes} memberName={member.name} />
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-gray-300 p-4 text-center text-sm text-gray-500">
              Click <strong>Find Schemes</strong> to run the eligibility engine against {member.name}'s profile
            </div>
          )}

          {member.notes && <div className="text-xs text-gray-500 italic">{member.notes}</div>}
        </div>
      )}
    </div>
  );
}

export default function FamilyPage() {
  const { data, error, isLoading, mutate } = useSWR('/api/family-members',
    (url) => fetch(API_BASE_URL + url).then(r => r.json()));
  const [showEditor, setShowEditor] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [schemeResults, setSchemeResults] = useState({});   // memberId -> result
  const [checkingId, setCheckingId] = useState(null);
  const [saveResult, setSaveResult] = useState(null);

  const members = data?.members || [];
  const setField = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const save = async () => {
    if (!form.name.trim()) { setMessage('Name is required.'); return; }
    setSaving(true); setMessage(''); setSaveResult(null);
    try {
      let res;
      if (editingId) {
        res = await fetch(`${API_BASE_URL}/api/family-members/${editingId}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
        }).then(r => r.json());
      } else {
        res = await fetch(`${API_BASE_URL}/api/family-members`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
        }).then(r => r.json());
      }
      if (!res.ok) throw new Error(res.error || 'Save failed');
      // After save, store engine result keyed by id
      const newId = res.id || editingId;
      if (newId && res.engine_result) {
        setSchemeResults(prev => ({ ...prev, [newId]: { engine_result: res.engine_result, tax_notes: res.tax_notes } }));
      }
      setSaveResult(res);
      setForm(DEFAULT_FORM); setEditingId(null); setShowEditor(false);
      setMessage(editingId ? 'Family member updated — scheme results ready below.' : 'Family member added — scheme results ready below.');
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (member) => {
    setForm({
      name: member.name || '', relationship: member.relationship || 'Daughter',
      date_of_birth: member.date_of_birth || '', citizenship: member.citizenship || 'USA',
      residential_status: member.residential_status || 'OCI Card Holder',
      oci_card_last4: member.oci_card_last4 || '', pan_last4: member.pan_last4 || '',
      living_in_india: member.living_in_india ?? true, currently_studying: member.currently_studying ?? false,
      institution_name: member.institution_name || '', course_details: member.course_details || '',
      currently_working: member.currently_working ?? false, employer_country: member.employer_country || '',
      has_india_income: member.has_india_income ?? false, india_income_notes: member.india_income_notes || '',
      notes: member.notes || '',
    });
    setEditingId(member.id); setShowEditor(true); setMessage('');
  };

  const deleteMember = async (id) => {
    if (!confirm('Delete this family member record?')) return;
    try {
      await fetch(`${API_BASE_URL}/api/family-members/${id}`, { method: 'DELETE' });
      setSchemeResults(prev => { const n = { ...prev }; delete n[id]; return n; });
      await mutate();
    } catch (e) { setMessage(`Error: ${e.message}`); }
  };

  const runSchemeCheck = async (id) => {
    setCheckingId(id);
    try {
      const res = await fetch(`${API_BASE_URL}/api/family-members/${id}/scheme-check`).then(r => r.json());
      if (res.ok) {
        setSchemeResults(prev => ({ ...prev, [id]: { engine_result: res.engine_result, tax_notes: res.tax_notes } }));
      } else {
        setMessage(`Scheme check error: ${res.error}`);
      }
    } catch (e) { setMessage(`Error: ${e.message}`); }
    finally { setCheckingId(null); }
  };

  if (isLoading) return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  if (error) return <div className="flex items-center gap-2 text-red-600 p-6"><AlertCircle className="w-6 h-6" /><span>Error loading family members</span></div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Users className="w-7 h-7 text-primary-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Family Members</h1>
            <p className="text-sm text-gray-500">Track dependents · Government scheme eligibility engine · Tax relevance</p>
          </div>
        </div>
        <button
          onClick={() => { setShowEditor(true); setEditingId(null); setForm(DEFAULT_FORM); setSaveResult(null); setMessage(''); }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 text-white text-sm hover:bg-primary-700">
          <Plus className="w-4 h-4" /> Add Family Member
        </button>
      </div>

      {message && (
        <div className={`flex items-center gap-2 rounded-lg p-3 text-sm ${message.startsWith('Error') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
          {message.startsWith('Error') ? <AlertCircle className="w-4 h-4 shrink-0" /> : <CheckCircle2 className="w-4 h-4 shrink-0" />}
          {message}
        </div>
      )}

      {/* Info banner */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <p className="font-semibold mb-1">🔍 Eligibility Engine</p>
        <p>Add a family member and click <strong>Find Schemes</strong>. The engine evaluates the profile against <strong>16 government and private schemes</strong> across education, banking, tax benefits, OCI rights, and girl-child programmes — factoring in citizenship, OCI status, age, gender, and relationship.</p>
      </div>

      {/* Editor */}
      {showEditor && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
          <h2 className="text-lg font-semibold text-gray-900">{editingId ? 'Edit Family Member' : 'Add Family Member'}</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[['name', 'Full Name *', 'text', 'e.g. Anika Hapatel']].map(([k, label, type, ph]) => (
              <div key={k}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input type={type} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={form[k]} onChange={e => setField(k, e.target.value)} placeholder={ph} />
              </div>
            ))}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Relationship</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" value={form.relationship} onChange={e => setField('relationship', e.target.value)}>
                {RELATIONSHIPS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth <span className="text-gray-400 font-normal">(important for age-based scheme eligibility)</span></label>
              <input type="date" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.date_of_birth} onChange={e => setField('date_of_birth', e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Citizenship</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" value={form.citizenship} onChange={e => setField('citizenship', e.target.value)}>
                {CITIZENSHIPS.map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Residential Status</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" value={form.residential_status} onChange={e => setField('residential_status', e.target.value)}>
                {RESIDENTIAL_STATUSES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">OCI Card (last 4 only)</label>
              <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" maxLength={6}
                value={form.oci_card_last4} onChange={e => setField('oci_card_last4', e.target.value)} placeholder="e.g. A1B2" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">PAN (last 4 only, if any)</label>
              <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" maxLength={4}
                value={form.pan_last4} onChange={e => setField('pan_last4', e.target.value.toUpperCase())} placeholder="e.g. 123P" />
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[['living_in_india', 'Living in India'], ['currently_studying', 'Currently studying'], ['currently_working', 'Currently working'], ['has_india_income', 'Has India income']].map(([k, l]) => (
              <label key={k} className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" className="w-4 h-4 rounded text-primary-600 border-gray-300"
                  checked={form[k]} onChange={e => setField(k, e.target.checked)} />
                <span className="text-sm text-gray-700">{l}</span>
              </label>
            ))}
          </div>

          {form.currently_studying && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-4 border-l-4 border-purple-200">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Institution</label>
                <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={form.institution_name} onChange={e => setField('institution_name', e.target.value)} placeholder="e.g. Amity University" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Course / Grade</label>
                <input className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  value={form.course_details} onChange={e => setField('course_details', e.target.value)} placeholder="e.g. Grade 10 / B.Tech CSE Yr1" />
              </div>
            </div>
          )}

          {form.has_india_income && (
            <div className="pl-4 border-l-4 border-amber-200">
              <label className="block text-sm font-medium text-gray-700 mb-1">India Income Notes</label>
              <textarea rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.india_income_notes} onChange={e => setField('india_income_notes', e.target.value)}
                placeholder="Describe source (e.g. NRO interest ₹12,000, TDS deducted)" />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Additional Notes</label>
            <textarea rows={2} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.notes} onChange={e => setField('notes', e.target.value)} placeholder="Any other relevant information..." />
          </div>

          <div className="flex gap-3">
            <button onClick={save} disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-primary-600 text-white text-sm hover:bg-primary-700 disabled:bg-gray-400">
              {saving ? <><Loader2 className="w-4 h-4 animate-spin" />Saving & running engine...</> : 'Save & Run Eligibility Engine'}
            </button>
            <button onClick={() => { setShowEditor(false); setEditingId(null); setForm(DEFAULT_FORM); setMessage(''); }}
              className="px-5 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Members */}
      {members.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Users className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p className="font-medium">No family members added yet</p>
          <p className="text-sm mt-1">Add a family member to check government scheme eligibility</p>
        </div>
      ) : (
        <div className="space-y-4">
          {members.map(m => (
            <MemberCard key={m.id} member={m}
              onEdit={startEdit} onDelete={deleteMember} onRefresh={runSchemeCheck}
              schemeResult={schemeResults[m.id] || null}
              checking={checkingId === m.id} />
          ))}
        </div>
      )}
    </div>
  );
}
