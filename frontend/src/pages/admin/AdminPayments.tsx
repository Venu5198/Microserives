import React, { useEffect, useState } from 'react';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { apiClient } from '../../api/client';

export const AdminPayments: React.FC = () => {
  const [payments, setPayments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refundingId, setRefundingId] = useState<string | null>(null);

  const fetchPayments = async () => {
    try {
      const res = await apiClient.get('/api/v1/payments');
      setPayments(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, []);

  const handleRefund = async (paymentId: string) => {
    if (!confirm('Issue full refund for this payment?')) return;
    setRefundingId(paymentId);
    try {
      await apiClient.post(`/api/v1/payments/${paymentId}/refund`, {
        reason: 'Admin issued refund',
        idempotency_key: `adm-ref-${paymentId}-${Date.now()}`,
      });
      await fetchPayments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to refund');
    } finally {
      setRefundingId(null);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Payment Transactions & Idempotency Audit</h2>
          <p className="text-xs text-gray-500">Every payment enforces idempotency keys to eliminate double-charges</p>
        </div>
        <button
          onClick={fetchPayments}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : payments.length === 0 ? (
        <div className="text-center py-12 text-sm text-gray-500">No payment transactions recorded yet.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase text-gray-700 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Payment ID</th>
                <th className="px-4 py-3">Order ID</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Card</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Idempotency Key</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {payments.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs font-bold text-gray-900">{p.id}</td>
                  <td className="px-4 py-3 font-mono text-xs">{p.order_id}</td>
                  <td className="px-4 py-3 font-bold text-gray-900">
                    ${(p.amount / 100).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-xs font-mono">•••• {p.card_last_four || '4242'}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        p.status === 'SUCCEEDED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : p.status === 'REFUNDED'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] text-gray-400 truncate max-w-[150px]">
                    {p.idempotency_key}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.status === 'SUCCEEDED' && (
                      <button
                        onClick={() => handleRefund(p.id)}
                        disabled={refundingId === p.id}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-red-700 border border-red-200 bg-red-50 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>{refundingId === p.id ? 'Refunding...' : 'Refund'}</span>
                      </button>
                    )}
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
