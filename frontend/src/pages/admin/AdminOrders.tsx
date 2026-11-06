import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { apiClient } from '../../api/client';

export const AdminOrders: React.FC = () => {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = async () => {
    try {
      const res = await apiClient.get('/api/v1/orders');
      setOrders(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Order Management & Saga Tracking</h2>
          <p className="text-xs text-gray-500">Monitor all customer orders across the distributed ecosystem</p>
        </div>
        <button
          onClick={fetchOrders}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-500">No customer orders recorded yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase text-gray-700 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Order Number</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {orders.map((o) => (
                <tr key={o.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-bold text-gray-900">{o.order_number}</td>
                  <td className="px-4 py-3 text-xs">{o.customer_email}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">
                    ${(o.total_amount / 100).toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        o.status === 'CONFIRMED' || o.status === 'SHIPPED' || o.status === 'DELIVERED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : o.status === 'CANCELLED'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {o.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/orders/${o.id}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700"
                    >
                      <span>View</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

