import React, { useEffect, useState } from 'react';
import { Bell, RefreshCw, Mail } from 'lucide-react';
import { apiClient } from '../../api/client';

export const AdminNotifications: React.FC = () => {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNotif, setSelectedNotif] = useState<any | null>(null);

  const fetchNotifications = async () => {
    try {
      const res = await apiClient.get('/api/v1/notifications');
      setNotifications(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Email Notification Audit Log</h2>
          <p className="text-xs text-gray-500">
            Real-time audit record of all asynchronous event-driven customer emails
          </p>
        </div>
        <button
          onClick={fetchNotifications}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : notifications.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-500">No notifications dispatched yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase text-gray-700 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Recipient</th>
                <th className="px-4 py-3">Template</th>
                <th className="px-4 py-3">Subject</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3 text-right">View Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {notifications.map((n) => (
                <tr key={n.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900 text-xs">{n.recipient_email}</td>
                  <td className="px-4 py-3 font-mono text-xs">{n.template_name}</td>
                  <td className="px-4 py-3 text-xs text-gray-800 font-medium truncate max-w-xs">{n.subject}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                      {n.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(n.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setSelectedNotif(n)}
                      className="text-xs font-semibold text-emerald-600 hover:underline"
                    >
                      Read Content
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Message Modal */}
      {selectedNotif && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl">
            <h3 className="text-base font-bold text-gray-900 mb-1 flex items-center gap-2">
              <Mail className="w-4 h-4 text-emerald-600" />
              {selectedNotif.subject}
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              To: {selectedNotif.recipient_email} | Sent at: {new Date(selectedNotif.created_at).toLocaleString()}
            </p>

            <div className="bg-gray-50 p-4 rounded-xl border border-gray-200 text-xs whitespace-pre-line font-mono text-gray-800 max-h-60 overflow-y-auto">
              {selectedNotif.content}
            </div>

            <div className="flex justify-end mt-4">
              <button
                onClick={() => setSelectedNotif(null)}
                className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 text-xs font-semibold rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
