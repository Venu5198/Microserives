import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Truck, CheckCircle2, Clock, XCircle, AlertTriangle, ShieldCheck } from 'lucide-react';
import { apiClient } from '../api/client';

export const OrderDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [order, setOrder] = useState<any>(null);
  const [saga, setSaga] = useState<any>(null);
  const [tracking, setTracking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('Found cheaper elsewhere');

  const fetchDetails = async () => {
    try {
      const orderRes = await apiClient.get(`/api/v1/orders/${id}`);
      setOrder(orderRes.data);

      try {
        const sagaRes = await apiClient.get(`/api/v1/orders/${id}/saga`);
        setSaga(sagaRes.data);
      } catch (e) {
        // May not be available for legacy
      }

      try {
        const trackRes = await apiClient.get(`/api/v1/orders/${id}/tracking`);
        setTracking(trackRes.data);
      } catch (e) {
        // Shipment may still be in progress
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [id]);

  const handleCancelOrder = async () => {
    setCancelling(true);
    try {
      const res = await apiClient.post(`/api/v1/orders/${id}/cancel`, { reason: cancelReason });
      setOrder(res.data);
      setCancelModalOpen(false);
      await fetchDetails();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to cancel order');
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center">
        <h2 className="text-xl font-bold text-gray-800">Order not found</h2>
        <Link to="/orders" className="text-emerald-600 mt-4 inline-block hover:underline">
          Back to my orders
        </Link>
      </div>
    );
  }

  const isCancellable = ['PENDING', 'AWAITING_PAYMENT', 'CONFIRMED'].includes(order.status);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Link to="/orders" className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 mb-6">
        <ArrowLeft className="w-4 h-4" />
        Back to my orders
      </Link>

      <div className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-6 mb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-extrabold text-gray-900">{order.order_number}</h1>
              <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">
                {order.status}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">Order ID: {order.id}</p>
          </div>

          {isCancellable && (
            <button
              onClick={() => setCancelModalOpen(true)}
              className="px-4 py-2 border border-red-300 text-red-600 hover:bg-red-50 text-sm font-semibold rounded-lg transition"
            >
              Cancel Order
            </button>
          )}
        </div>

        {/* Order Items */}
        <div className="space-y-4 mb-6">
          <h2 className="text-base font-bold text-gray-900">Ordered Items</h2>
          <div className="divide-y divide-gray-100">
            {order.items.map((item: any, idx: number) => (
              <div key={idx} className="py-3 flex justify-between items-center text-sm">
                <div>
                  <div className="font-semibold text-gray-900">{item.product_name}</div>
                  <div className="text-xs text-gray-500">
                    Qty: {item.quantity} × ${(item.unit_price / 100).toFixed(2)}
                  </div>
                </div>
                <div className="font-bold text-gray-900">${(item.subtotal / 100).toFixed(2)}</div>
              </div>
            ))}
          </div>

          <div className="border-t border-gray-200 pt-4 flex justify-between items-center text-lg font-bold text-gray-900">
            <span>Total Amount Paid</span>
            <span>${(order.total_amount / 100).toFixed(2)}</span>
          </div>
        </div>

        {/* Shipping Address */}
        <div className="bg-gray-50 rounded-xl p-4 text-xs text-gray-600 mb-6">
          <span className="font-bold text-gray-800 block mb-1">Shipping Destination:</span>
          <p>{order.shipping_address.street}</p>
          <p>{order.shipping_address.city}, {order.shipping_address.state} {order.shipping_address.postal_code}</p>
          <p>{order.shipping_address.country}</p>
        </div>

        {/* Live Shipment Tracking Section */}
        {tracking && (
          <div className="border-t border-gray-100 pt-6 mt-6">
            <h2 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-4">
              <Truck className="w-5 h-5 text-emerald-600" />
              Live Shipment Tracking: {tracking.tracking_number} ({tracking.carrier})
            </h2>

            <div className="space-y-4 pl-4 border-l-2 border-emerald-500 ml-2">
              {tracking.events.map((ev: any, idx: number) => (
                <div key={idx} className="relative">
                  <div className="absolute -left-[23px] top-1 w-3 h-3 rounded-full bg-emerald-600 border-2 border-white"></div>
                  <div className="text-sm font-semibold text-gray-900">{ev.status} - {ev.location}</div>
                  <div className="text-xs text-gray-500">{ev.description}</div>
                  <div className="text-[11px] text-gray-400">
                    {new Date(ev.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Saga Execution Audit View */}
        {saga && (
          <div className="border-t border-gray-100 pt-6 mt-6">
            <h2 className="text-sm font-bold text-gray-700 flex items-center gap-2 mb-3">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              Distributed Saga Transaction Trace
            </h2>
            <div className="bg-gray-900 text-gray-200 rounded-xl p-4 text-xs font-mono overflow-x-auto">
              <p className="text-emerald-400 mb-2">// Current State: {saga.current_state}</p>
              {saga.history.map((step: any, idx: number) => (
                <div key={idx} className="mb-1">
                  <span className="text-gray-500">[{new Date(step.timestamp).toLocaleTimeString()}]</span>{' '}
                  <span className="text-amber-300 font-bold">{step.state}</span>:{' '}
                  <span>{JSON.stringify(step.details)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cancellation Modal */}
      {cancelModalOpen && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Confirm Order Cancellation</h3>
            <p className="text-sm text-gray-600 mb-4">
              Cancelling will trigger automated compensation: any charged amount will be refunded immediately,
              and reserved inventory will be released back to the catalog.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-700 mb-1">Reason for cancellation</label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setCancelModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Keep Order
              </button>
              <button
                onClick={handleCancelOrder}
                disabled={cancelling}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg shadow disabled:opacity-50"
              >
                {cancelling ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
