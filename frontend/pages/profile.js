import { useState, useEffect } from 'react';
import { User, Users, MapPin, FileText, Loader2, AlertCircle, Check } from 'lucide-react';
import useSWR from 'swr';

const fetcher = (url) => fetch(url).then((res) => res.json());

export default function Profile() {
  const { data: taxpayersData, error, isLoading, mutate } = useSWR('/api/taxpayers', fetcher);
  const [selectedTaxpayer, setSelectedTaxpayer] = useState(1);
  const [editMode, setEditMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (taxpayersData) {
      const taxpayers = taxpayersData?.taxpayers || [];
      const current = taxpayers.find((t) => t.id === selectedTaxpayer);
      if (current) {
        setFormData({
          name: current.name,
          citizenship: current.citizenship,
          pan_last4: current.pan_last4 || '',
          has_dependent_child: current.has_dependent_child,
        });
      }
    }
  }, [selectedTaxpayer, taxpayersData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card border-danger-300 bg-danger-50 p-6">
        <AlertCircle className="w-5 h-5 text-danger-600 mb-2" />
        <p className="text-danger-700">Failed to load taxpayer profile</p>
      </div>
    );
  }

  const taxpayers = taxpayersData?.taxpayers || [];
  const current = taxpayers.find((t) => t.id === selectedTaxpayer);

  const handleSave = async () => {
    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`/api/taxpayers/${selectedTaxpayer}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      const result = await res.json();
      if (result.ok) {
        setMessage('✅ Profile saved successfully');
        setEditMode(false);
        mutate(); // Refresh data
        setTimeout(() => setMessage(''), 3000);
      } else {
        setMessage('❌ Error: ' + (result.error || 'Unknown error'));
      }
    } catch (err) {
      setMessage('❌ Error: ' + err.message);
    }
    setLoading(false);
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value,
    });
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">👤 Household Profile</h1>
        <p className="text-lg text-gray-600">Manage taxpayer information and family details</p>
      </div>

      {/* Taxpayer Selection */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-4">Select Taxpayer</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {taxpayers.map((tp) => (
            <div
              key={tp.id}
              onClick={() => {
                setSelectedTaxpayer(tp.id);
                setEditMode(false);
                setMessage('');
              }}
              className={`card p-6 cursor-pointer transition ${
                selectedTaxpayer === tp.id
                  ? 'border-primary-500 border-2 bg-primary-50'
                  : 'hover:shadow-md'
              }`}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-bold text-lg text-gray-900">{tp.name}</h3>
                  <p className="text-sm text-gray-600">{tp.citizenship} Citizen</p>
                </div>
                <span className="badge badge-primary">{tp.id === 1 ? 'NRI' : 'RNOR'}</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-600">PAN: {tp.pan_last4 || 'Not provided'}</span>
                </div>
                {tp.has_dependent_child && (
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-600">Has dependent child</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Profile Details */}
      {current && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900">{current.name}'s Profile</h2>
            <button
              onClick={() => setEditMode(!editMode)}
              className={editMode ? 'btn-secondary' : 'btn-primary'}
            >
              {editMode ? 'Cancel' : 'Edit Profile'}
            </button>
          </div>

          {/* Message */}
          {message && (
            <div className={`card p-4 border ${message.includes('✅') ? 'border-success-300 bg-success-50' : 'border-danger-300 bg-danger-50'}`}>
              <p className={message.includes('✅') ? 'text-success-700' : 'text-danger-700'}>{message}</p>
            </div>
          )}

          {/* Basic Information */}
          <div className="card p-6">
            <h3 className="font-bold text-lg text-gray-900 mb-6">Basic Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                <input
                  type="text"
                  name="name"
                  value={formData.name || ''}
                  onChange={handleInputChange}
                  disabled={!editMode}
                  className={`input w-full ${!editMode && 'bg-gray-50'}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Citizenship</label>
                <input
                  type="text"
                  name="citizenship"
                  value={formData.citizenship || ''}
                  onChange={handleInputChange}
                  disabled={!editMode}
                  className={`input w-full ${!editMode && 'bg-gray-50'}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">PAN (Last 4)</label>
                <input
                  type="text"
                  name="pan_last4"
                  value={formData.pan_last4 || ''}
                  onChange={handleInputChange}
                  disabled={!editMode}
                  placeholder="XXXX"
                  maxLength="4"
                  className={`input w-full ${!editMode && 'bg-gray-50'}`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                <div className={`input w-full bg-gray-50 flex items-center ${current.id === 1 ? 'text-orange-600' : 'text-purple-600'}`}>
                  {current.id === 1 ? '🌍 Non-Resident (NRI)' : '🏘️ Resident Not Ordinary (RNOR)'}
                </div>
              </div>
            </div>
          </div>

          {/* Dependent Information */}
          <div className="card p-6">
            <h3 className="font-bold text-lg text-gray-900 mb-6">Family & Dependents</h3>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  name="has_dependent_child"
                  checked={formData.has_dependent_child || false}
                  onChange={handleInputChange}
                  disabled={!editMode}
                  className="w-5 h-5 rounded border-gray-300"
                />
                <label className="text-gray-700 font-medium">Has dependent child</label>
              </div>

              {(formData.has_dependent_child || current.has_dependent_child) && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-4 mt-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Child's Name</label>
                      <input type="text" disabled className="input w-full bg-gray-50" placeholder="Dependent name" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Age (Years)</label>
                      <input type="number" disabled className="input w-full bg-gray-50" placeholder="Age" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Country of Residence</label>
                      <input
                        type="text"
                        value={current.dependent_child_country_of_residence || 'India'}
                        disabled
                        className="input w-full bg-gray-50"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Citizenship</label>
                      <input type="text" disabled className="input w-full bg-gray-50" placeholder="Citizenship" />
                    </div>
                  </div>

                  {current.is_eligible_for_80ac && (
                    <div className="bg-success-50 border border-success-300 rounded p-3 flex items-start gap-3">
                      <span className="text-2xl">✅</span>
                      <div>
                        <p className="font-medium text-success-900">Section 80AC Eligible</p>
                        <p className="text-sm text-success-700">Dependent child qualifies for Sukanya Samriddhi deduction (₹1,50,000/year)</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Residency Information */}
          <div className="card p-6">
            <h3 className="font-bold text-lg text-gray-900 mb-6 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-primary-600" />
              Residency Status
            </h3>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-sm text-gray-700 mb-4">
                {current.id === 1
                  ? 'You are registered as an NRI (Non-Resident Individual). This status requires maintaining <60 days presence in India (current FY) AND <183 days in prior 4 FYs.'
                  : 'You are registered as RNOR (Resident Not Ordinarily Resident). This status applies when you are resident but not for 2 of prior 10 years.'}
              </p>
              <button className="btn-secondary text-sm">
                Update Residency Details →
              </button>
            </div>
          </div>

          {editMode && (
            <div className="flex gap-3">
              <button
                onClick={handleSave}
                disabled={loading}
                className="btn-primary"
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                onClick={() => {
                  setEditMode(false);
                  setMessage('');
                }}
                className="btn-secondary"
              >
                Discard
              </button>
            </div>
          )}
        </div>
      )}

      {/* CTA */}
      <div className="bg-gradient-to-r from-primary-600 to-blue-600 rounded-xl p-8 text-white">
        <h3 className="text-2xl font-bold mb-4">Manage Your Household</h3>
        <p className="mb-6 text-blue-100">
          Keep your family information up-to-date to ensure accurate tax calculations and deduction eligibility.
        </p>
        <a href="/income">
          <button className="bg-white text-primary-600 font-medium px-6 py-2 rounded-lg hover:bg-blue-50 transition">
            Complete Income Details →
          </button>
        </a>
      </div>
    </div>
  );
}
