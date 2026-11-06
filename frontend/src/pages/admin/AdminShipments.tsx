import React, { useEffect, useState } from 'react';
import { Truck, RefreshCw, Send } from 'lucide-react';
import { apiClient } from '../../api/client';

export const AdminShipments: React.FC = () => {
  const [shipments, setShipments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedShipment, setSelectedShipment] = useState<any | null>(null);
  const [newStatus, setNewStatus] = useState('IN_TRANSIT');
  const [location, setLocation] = useState('Metro Dispatch Hub');
  const [notes, setNotes] = useState('Package scanned onto delivery vehicle');
  const [updating, setUpdating] = useState(false);

  const fetchShipments = async () => {
    try {
      const res = await apiClient.get('/api/v1/shipments');
      setShipments(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchShipments();
  }, []);

  const handleUpdateStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedShipment) return;
    setUpdating(true);
    try {
      await apiClient.patch(`/api/v1/shipments/${selectedShipment.id}/status`, {
        status: newStatus,
        location,
        notes,
      });
      setSelectedShipment(null);
      await fetchShipments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update shipment status');
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Shipments & Courier Simulation</h2>
          <p className="text-xs text-gray-500">
            Simulate realistic carrier check-ins, scans, and final delivery events
          </p>
        </div>
        <button
          onClick={fetchShipments}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : shipments.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-500">No shipments generated yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase text-gray-700 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Tracking #</th>
                <th className="px-4 py-3">Order ID</th>
                <th className="px-4 py-3">Carrier</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Latest Event</th>
                <th className="px-4 py-3 text-right">Simulate Courier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {shipments.map((s) => {
                const latestEvent = s.events && s.events.length > 0 ? s.events[s.events.length - 1] : null;
                return (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs font-bold text-gray-900">
                      {s.tracking_number}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{s.order_id}</td>
                    <td className="px-4 py-3 text-xs">{s.carrier}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-semibold ${
                          s.status === 'DELIVERED'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {latestEvent ? `${latestEvent.status} @ ${latestEvent.location}` : 'Label Created'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {s.status !== 'DELIVERED' && (
                        <button
                          onClick={() => {
                            setSelectedShipment(s);
                            setNewStatus(s.status === 'CREATED' ? 'PICKED_UP' : (s.status === 'PICKED_UP' ? 'IN_TRANSIT' : (s.status === 'IN_TRANSIT' ? 'OUT_FOR_DELIVERY' : 'DELIVERED')));
                          }}
                          className="px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200 bg-emerald-50 rounded hover:bg-emerald-100"
                        >
                          Update Status
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Simulator Modal */}
      {selectedShipment && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-base font-bold text-gray-900 mb-1 flex items-center gap-2">
              <Truck className="w-5 h-5 text-emerald-600" />
              Simulate Courier Scan
            </h3>
            <p className="text-xs text-gray-500 mb-4 font-mono">
              Tracking: {selectedShipment.tracking_number}
            </p>

            <form onSubmit={handleUpdateStatus} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">New Shipment Status</label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                >
                  <option value="PICKED_UP">PICKED_UP (Carrier picked up package)</option>
                  <option value="IN_TRANSIT">IN_TRANSIT (Sorted at regional hub)</option>
                  <option value="OUT_FOR_DELIVERY">OUT_FOR_DELIVERY (On local delivery van)</option>
                  <option value="DELIVERED">DELIVERED (Delivered to customer doorstep)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Scan Location</label>
                <input
                  type="text"
                  required
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Carrier Notes</label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setSelectedShipment(null)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updating}
                  className="px-3.5 py-1.5 bg-emerald-600 text-white font-semibold text-xs rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                >
                  {updating ? 'Publishing Event...' : 'Broadcast Scan Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
