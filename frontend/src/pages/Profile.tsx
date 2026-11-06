import React, { useEffect, useState } from 'react';
import { User, MapPin, Plus, Check } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const Profile: React.FC = () => {
  const { user } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [newAddress, setNewAddress] = useState({
    title: 'Home',
    street: '',
    city: '',
    state: '',
    postal_code: '',
    country: 'US',
    is_default: true,
  });

  const fetchProfile = async () => {
    try {
      const res = await apiClient.get('/api/v1/users/me');
      setProfile(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleAddAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.post('/api/v1/users/me/addresses', newAddress);
      setShowAddressForm(false);
      setNewAddress({
        title: 'Home',
        street: '',
        city: '',
        state: '',
        postal_code: '',
        country: 'US',
        is_default: false,
      });
      await fetchProfile();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save address');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm">
        <div className="flex items-center gap-4 border-b border-gray-100 pb-6 mb-6">
          <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-xl">
            {profile?.first_name ? profile.first_name[0] : 'U'}
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900">
              {profile?.first_name} {profile?.last_name}
            </h1>
            <p className="text-sm text-gray-500">{profile?.email}</p>
            <span className="inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700">
              Role: {profile?.role}
            </span>
          </div>
        </div>

        {/* Address Book */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-emerald-600" />
              Saved Addresses
            </h2>
            <button
              onClick={() => setShowAddressForm(!showAddressForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition"
            >
              <Plus className="w-4 h-4" /> Add Address
            </button>
          </div>

          {showAddressForm && (
            <form onSubmit={handleAddAddress} className="mb-6 p-4 bg-gray-50 rounded-xl border border-gray-200 space-y-3">
              <h3 className="text-xs font-bold text-gray-700 uppercase">New Address Details</h3>
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="Address Title (e.g. Home, Office)"
                  required
                  value={newAddress.title}
                  onChange={(e) => setNewAddress({ ...newAddress, title: e.target.value })}
                  className="px-3 py-1.5 border rounded-lg text-sm bg-white"
                />
                <input
                  type="text"
                  placeholder="Street"
                  required
                  value={newAddress.street}
                  onChange={(e) => setNewAddress({ ...newAddress, street: e.target.value })}
                  className="px-3 py-1.5 border rounded-lg text-sm bg-white"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <input
                  type="text"
                  placeholder="City"
                  required
                  value={newAddress.city}
                  onChange={(e) => setNewAddress({ ...newAddress, city: e.target.value })}
                  className="px-3 py-1.5 border rounded-lg text-sm bg-white"
                />
                <input
                  type="text"
                  placeholder="State"
                  required
                  value={newAddress.state}
                  onChange={(e) => setNewAddress({ ...newAddress, state: e.target.value })}
                  className="px-3 py-1.5 border rounded-lg text-sm bg-white"
                />
                <input
                  type="text"
                  placeholder="Postal Code"
                  required
                  value={newAddress.postal_code}
                  onChange={(e) => setNewAddress({ ...newAddress, postal_code: e.target.value })}
                  className="px-3 py-1.5 border rounded-lg text-sm bg-white"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddressForm(false)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-semibold hover:bg-emerald-700"
                >
                  Save Address
                </button>
              </div>
            </form>
          )}

          {profile?.addresses?.length === 0 ? (
            <p className="text-sm text-gray-500 italic">No addresses saved yet.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {profile?.addresses?.map((addr: any) => (
                <div key={addr.id} className="p-4 border border-gray-200 rounded-xl bg-gray-50 text-xs text-gray-700 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-gray-900 text-sm">{addr.title}</span>
                    {addr.is_default && (
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded font-semibold text-[10px]">
                        Default
                      </span>
                    )}
                  </div>
                  <p>{addr.street}</p>
                  <p>{addr.city}, {addr.state} {addr.postal_code}</p>
                  <p>{addr.country}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
