import { useEffect, useMemo, useState } from 'react';
import { User, Save, Loader2, AlertCircle, CheckCircle2, Pencil, X, MapPin } from 'lucide-react';
import useSWR from 'swr';
import { fetcher } from '../lib/api';
import { useCaseContext } from '../lib/case-context';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const EMPTY_PROFILE = {
  name: '',
  pan_last4: '',
  pan_full: '',
  citizenship: 'Indian',
  date_of_birth: '',
  marital_status: '',
  occupation: '',
  employer_name: '',
  email: '',
  mobile_country_code: '+91',
  mobile_primary: '',
  aadhaar_mobile_country_code: '+91',
  aadhaar_mobile: '',
  alt_mobiles: '',
  aadhaar_last4: '',
  aadhaar_full: '',
  passport_last4: '',
  passport_full: '',
  emergency_contact_name: '',
  emergency_contact_mobile: '',
  permanent_address: '',
  mailing_address: '',
  city: '',
  state: '',
  postal_code: '',
  country: 'India',
  refund_account_last4: '',
  refund_ifsc: '',
  preferred_contact_mode: 'email',
  communication_notes: '',
};

const COUNTRY_OPTIONS = [
  { label: 'India', value: 'India', code: '+91' },
  { label: 'US', value: 'US', code: '+1' },
];

const label = (v) => (v === null || v === undefined || v === '' ? '—' : v);
const masked = (v) => {
  if (!v) return '—';
  const str = String(v);
  if (str.length <= 4) return str;
  return `${'•'.repeat(Math.max(0, str.length - 4))}${str.slice(-4)}`;
};
const last4 = (v) => {
  if (!v) return '';
  const s = String(v);
  return s.length <= 4 ? s : s.slice(-4);
};

function ReadItem({ title, value }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
      <p className="text-xs text-gray-500">{title}</p>
      <p className="text-sm font-medium text-gray-900 mt-1 break-words">{label(value)}</p>
    </div>
  );
}

function TextInput({ title, value, onChange, type = 'text', placeholder = '', maxLength }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-gray-700">{title}</span>
      <input
        type={type}
        value={value || ''}
        onChange={onChange}
        maxLength={maxLength}
        placeholder={placeholder}
        className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2"
      />
    </label>
  );
}

export default function Profile() {
  const { selectedTaxpayerId, selectedMember, selectedCase } = useCaseContext();
  const taxpayerId = selectedTaxpayerId || selectedMember?.id;
  const { data, error, isLoading, mutate } = useSWR(
    taxpayerId ? apiUrl(`/api/taxpayers/${taxpayerId}/profile`) : null,
    fetcher
  );
  const [formData, setFormData] = useState(EMPTY_PROFILE);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [message, setMessage] = useState('');
  const [postalHint, setPostalHint] = useState('');

  const hydrateFromData = () => {
    if (!data) return;
    setFormData({
      ...EMPTY_PROFILE,
      ...data.taxpayer,
      ...(data.profile || {}),
      date_of_birth: data.profile?.date_of_birth || '',
    });
  };

  useEffect(() => {
    if (!data) return;
    hydrateFromData();
    setIsEditing(false);
  }, [data]);

  const validationError = useMemo(() => {
    if (formData.pan_last4 && !/^[A-Za-z0-9]{4}$/.test(formData.pan_last4)) return 'PAN Last 4 must be exactly 4 alphanumeric characters.';
    if (formData.pan_full && !/^[A-Za-z]{5}\d{4}[A-Za-z]$/.test(formData.pan_full)) return 'PAN format must be like ABCDE1234F.';
    if (formData.mobile_primary && !/^\d{10}$/.test(formData.mobile_primary)) return 'Primary mobile must be 10 digits.';
    if (formData.aadhaar_mobile && !/^\d{10}$/.test(formData.aadhaar_mobile)) return 'Aadhaar-linked mobile must be 10 digits.';
    if (formData.aadhaar_full && !/^\d{12}$/.test(formData.aadhaar_full)) return 'Aadhaar must be 12 digits.';
    if (formData.aadhaar_last4 && !/^\d{4}$/.test(formData.aadhaar_last4)) return 'Aadhaar last 4 must be 4 digits.';
    if (formData.refund_account_last4 && !/^\d{4}$/.test(formData.refund_account_last4)) return 'Refund account last 4 must be 4 digits.';
    if (formData.country === 'India' && formData.postal_code && !/^\d{6}$/.test(formData.postal_code)) return 'Indian PIN must be 6 digits.';
    if (formData.country === 'US' && formData.postal_code && !/^\d{5}(\d{4})?$/.test(formData.postal_code.replace(/-/g, ''))) return 'US ZIP must be 5 or 9 digits.';
    return '';
  }, [formData]);

  const setField = (key, value) => setFormData((prev) => ({ ...prev, [key]: value }));

  const lookupPostal = async () => {
    if (!formData.postal_code || !formData.country) return;
    setPostalHint('Validating postal code...');
    try {
      const res = await fetch(apiUrl(`/api/reference/postal-lookup?country=${encodeURIComponent(formData.country)}&postal_code=${encodeURIComponent(formData.postal_code)}`));
      const payload = await res.json();
      if (payload.ok && payload.valid) {
        setFormData((prev) => ({
          ...prev,
          city: payload.city || prev.city,
          state: payload.state || prev.state,
          country: payload.suggested_country || prev.country,
        }));
        setPostalHint(`Validated: ${payload.city || '—'}, ${payload.state || '—'}`);
      } else {
        setPostalHint(payload.message || 'Postal code not found');
      }
    } catch (e) {
      setPostalHint(`Lookup failed: ${e.message}`);
    }
  };

  const onCountryChange = (country) => {
    const selected = COUNTRY_OPTIONS.find((c) => c.value === country);
    setFormData((prev) => ({
      ...prev,
      country,
      mobile_country_code: selected?.code || prev.mobile_country_code,
      aadhaar_mobile_country_code: selected?.code || prev.aadhaar_mobile_country_code,
    }));
  };

  const saveProfile = async () => {
    if (!taxpayerId || validationError) return;
    setSaving(true);
    setMessage('');
    try {
      const payload = {
        ...formData,
        pan_last4: (formData.pan_last4 || '').toUpperCase(),
        pan_full: (formData.pan_full || '').toUpperCase(),
        passport_full: (formData.passport_full || '').toUpperCase(),
        passport_last4: (formData.passport_last4 || '').toUpperCase(),
        refund_ifsc: (formData.refund_ifsc || '').toUpperCase(),
      };
      const res = await fetch(apiUrl(`/api/taxpayers/${taxpayerId}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (!result.ok) throw new Error(result.error || 'Failed to save profile');
      setMessage('Profile updated successfully.');
      setIsEditing(false);
      await mutate();
    } catch (e) {
      setMessage(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen"><Loader2 className="w-8 h-8 animate-spin text-primary-600" /></div>;
  }

  if (error) {
    return <div className="flex items-center gap-2 text-red-600"><AlertCircle className="w-6 h-6" /><span>Error loading profile</span></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <User className="w-8 h-8 text-primary-600" />
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Taxpayer Profile</h1>
            <p className="text-gray-600">
              Linked to {selectedMember?.name || 'taxpayer'} • FY {selectedCase?.financial_year || '—'} • AY {selectedCase?.assessment_year || '—'}
            </p>
          </div>
        </div>
        {!isEditing ? (
          <button onClick={() => { setIsEditing(true); setMessage(''); }} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2 hover:bg-primary-700">
            <Pencil className="w-4 h-4" /> Edit Profile
          </button>
        ) : (
          <button onClick={() => { setIsEditing(false); setMessage(''); hydrateFromData(); }} className="inline-flex items-center gap-2 rounded-lg bg-gray-200 text-gray-900 px-4 py-2 hover:bg-gray-300">
            <X className="w-4 h-4" /> Cancel
          </button>
        )}
      </div>

      {validationError && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{validationError}</div>}
      {postalHint && <div className="p-3 rounded-lg bg-blue-50 text-blue-700 text-sm">{postalHint}</div>}

      {!isEditing ? (
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Identity</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <ReadItem title="Full Name" value={formData.name} />
              <ReadItem title="PAN" value={masked(formData.pan_full)} />
              <ReadItem title="PAN Last 4 (auto)" value={formData.pan_last4 || last4(formData.pan_full)} />
              <ReadItem title="Aadhaar" value={masked(formData.aadhaar_full)} />
              <ReadItem title="Aadhaar Last 4 (auto)" value={formData.aadhaar_last4 || last4(formData.aadhaar_full)} />
              <ReadItem title="Passport" value={masked(formData.passport_full)} />
              <ReadItem title="Passport Last 4 (auto)" value={formData.passport_last4 || last4(formData.passport_full)} />
              <ReadItem title="Citizenship" value={formData.citizenship} />
              <ReadItem title="Date of Birth" value={formData.date_of_birth} />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Contact & Address</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <ReadItem title="Email" value={formData.email} />
              <ReadItem title="Primary Mobile" value={`${label(formData.mobile_country_code)} ${label(formData.mobile_primary)}`} />
              <ReadItem title="Aadhaar-linked Mobile" value={`${label(formData.aadhaar_mobile_country_code)} ${label(formData.aadhaar_mobile)}`} />
              <ReadItem title="Alternative Mobile(s)" value={formData.alt_mobiles} />
              <ReadItem title="City" value={formData.city} />
              <ReadItem title="State" value={formData.state} />
              <ReadItem title="Postal Code" value={formData.postal_code} />
              <ReadItem title="Country" value={formData.country} />
              <ReadItem title="Preferred Contact Mode" value={formData.preferred_contact_mode} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <ReadItem title="Permanent Address" value={formData.permanent_address} />
              <ReadItem title="Current Mailing Address" value={formData.mailing_address} />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Compliance & Refund</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <ReadItem title="Marital Status" value={formData.marital_status} />
              <ReadItem title="Occupation" value={formData.occupation} />
              <ReadItem title="Employer Name" value={formData.employer_name} />
              <ReadItem title="Emergency Contact Name" value={formData.emergency_contact_name} />
              <ReadItem title="Emergency Contact Mobile" value={formData.emergency_contact_mobile} />
              <ReadItem title="Refund A/c Last 4" value={formData.refund_account_last4} />
              <ReadItem title="Refund IFSC" value={formData.refund_ifsc} />
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Identity</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <TextInput title="Full Name" value={formData.name} onChange={(e) => setField('name', e.target.value)} />
              <TextInput title="PAN (Full)" value={formData.pan_full} onChange={(e) => setField('pan_full', e.target.value.toUpperCase())} maxLength={10} />
              <TextInput title="Aadhaar (Full)" value={formData.aadhaar_full} onChange={(e) => setField('aadhaar_full', e.target.value.replace(/\D/g, ''))} maxLength={12} />
              <TextInput title="Passport (Full)" value={formData.passport_full} onChange={(e) => setField('passport_full', e.target.value.toUpperCase())} maxLength={30} />
              <ReadItem title="PAN Last 4 (auto from full)" value={last4(formData.pan_full)} />
              <ReadItem title="Aadhaar Last 4 (auto from full)" value={last4(formData.aadhaar_full)} />
              <ReadItem title="Passport Last 4 (auto from full)" value={last4(formData.passport_full)} />
              <TextInput title="Date of Birth" type="date" value={formData.date_of_birth} onChange={(e) => setField('date_of_birth', e.target.value)} />
              <TextInput title="Citizenship" value={formData.citizenship} onChange={(e) => setField('citizenship', e.target.value)} />
            </div>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Contact</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <TextInput title="Email" type="email" value={formData.email} onChange={(e) => setField('email', e.target.value)} />
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Country</span>
                <select value={formData.country} onChange={(e) => onCountryChange(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
                  {COUNTRY_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Primary Mobile</span>
                <div className="mt-1 flex gap-2">
                  <select value={formData.mobile_country_code || '+91'} onChange={(e) => setField('mobile_country_code', e.target.value)} className="w-24 rounded-lg border border-gray-300 px-2 py-2">
                    <option value="+91">+91</option>
                    <option value="+1">+1</option>
                  </select>
                  <input value={formData.mobile_primary || ''} onChange={(e) => setField('mobile_primary', e.target.value.replace(/\D/g, ''))} maxLength={10} className="flex-1 rounded-lg border border-gray-300 px-3 py-2" />
                </div>
              </label>
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Aadhaar-linked Mobile</span>
                <div className="mt-1 flex gap-2">
                  <select value={formData.aadhaar_mobile_country_code || '+91'} onChange={(e) => setField('aadhaar_mobile_country_code', e.target.value)} className="w-24 rounded-lg border border-gray-300 px-2 py-2">
                    <option value="+91">+91</option>
                    <option value="+1">+1</option>
                  </select>
                  <input value={formData.aadhaar_mobile || ''} onChange={(e) => setField('aadhaar_mobile', e.target.value.replace(/\D/g, ''))} maxLength={10} className="flex-1 rounded-lg border border-gray-300 px-3 py-2" />
                </div>
              </label>
              <TextInput title="Alternative Mobile(s)" value={formData.alt_mobiles} onChange={(e) => setField('alt_mobiles', e.target.value)} placeholder="Comma separated" />
              <TextInput title="Emergency Contact Name" value={formData.emergency_contact_name} onChange={(e) => setField('emergency_contact_name', e.target.value)} />
              <TextInput title="Emergency Contact Mobile" value={formData.emergency_contact_mobile} onChange={(e) => setField('emergency_contact_mobile', e.target.value.replace(/\D/g, ''))} maxLength={10} />
            </div>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Address & Validation</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <TextInput title="Postal Code" value={formData.postal_code} onChange={(e) => setField('postal_code', e.target.value.trim())} />
              <button onClick={lookupPostal} type="button" className="h-fit mt-7 inline-flex items-center gap-2 rounded-lg bg-blue-600 text-white px-3 py-2 hover:bg-blue-700">
                <MapPin className="w-4 h-4" /> Validate postal code
              </button>
              <TextInput title="City" value={formData.city} onChange={(e) => setField('city', e.target.value)} />
              <TextInput title="State" value={formData.state} onChange={(e) => setField('state', e.target.value)} />
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Preferred Contact Mode</span>
                <select value={formData.preferred_contact_mode || 'email'} onChange={(e) => setField('preferred_contact_mode', e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
                  <option value="email">Email</option>
                  <option value="mobile">Mobile</option>
                  <option value="whatsapp">WhatsApp</option>
                </select>
              </label>
              <TextInput title="Marital Status" value={formData.marital_status} onChange={(e) => setField('marital_status', e.target.value)} placeholder="Single / Married" />
              <TextInput title="Occupation" value={formData.occupation} onChange={(e) => setField('occupation', e.target.value)} />
              <TextInput title="Employer Name" value={formData.employer_name} onChange={(e) => setField('employer_name', e.target.value)} />
              <TextInput title="Refund A/c Last 4" value={formData.refund_account_last4} onChange={(e) => setField('refund_account_last4', e.target.value.replace(/\D/g, ''))} maxLength={4} />
              <TextInput title="Refund IFSC" value={formData.refund_ifsc} onChange={(e) => setField('refund_ifsc', e.target.value.toUpperCase())} maxLength={20} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Permanent Address</span>
                <textarea value={formData.permanent_address || ''} onChange={(e) => setField('permanent_address', e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-20" />
              </label>
              <label className="block">
                <span className="block text-sm font-medium text-gray-700">Current Mailing Address</span>
                <textarea value={formData.mailing_address || ''} onChange={(e) => setField('mailing_address', e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-20" />
              </label>
            </div>
            <label className="block mt-4">
              <span className="block text-sm font-medium text-gray-700">Communication Notes</span>
              <textarea value={formData.communication_notes || ''} onChange={(e) => setField('communication_notes', e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 min-h-20" />
            </label>
          </div>

          <button onClick={saveProfile} disabled={saving || !!validationError} className="inline-flex items-center gap-2 rounded-lg bg-primary-600 text-white px-4 py-2 hover:bg-primary-700 disabled:bg-gray-400">
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      )}

      {message && (
        <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${message.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          <CheckCircle2 className="w-4 h-4" />
          {message}
        </div>
      )}
    </div>
  );
}
