import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CreditCard, CheckCircle, AlertCircle, Loader2, ArrowRight } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const Checkout: React.FC = () => {
  const [cart, setCart] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [sagaStatus, setSagaStatus] = useState<string | null>(null);
  const [createdOrderId, setCreatedOrderId] = useState<string | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);

  const [address, setAddress] = useState({
    street: '123 Market Street',
    city: 'San Francisco',
    state: 'CA',
    postal_code: '94105',
    country: 'US',
  });

  const [cardSimulation, setCardSimulation] = useState<'success' | 'fail'>('success');
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchCartAndProfile = async () => {
      try {
        const cartRes = await apiClient.get('/api/v1/cart');
        setCart(cartRes.data);

        // Prepopulate address if user has saved addresses
        const profRes = await apiClient.get('/api/v1/users/me');
        if (profRes.data.addresses && profRes.data.addresses.length > 0) {
          const defaultAddr = profRes.data.addresses.find((a: any) => a.is_default) || profRes.data.addresses[0];
          setAddress({
            street: defaultAddr.street,
            city: defaultAddr.city,
            state: defaultAddr.state,
            postal_code: defaultAddr.postal_code,
            country: defaultAddr.country || 'US',
          });
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchCartAndProfile();
  }, []);

  const handlePlaceOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cart || cart.items.length === 0) return;

    setSubmitting(true);
    setOrderError(null);
    setSagaStatus('SUBMITTING_ORDER');

    try {
      const orderPayload = {
        items: cart.items.map((it: any) => ({
          product_id: it.product_id,
          product_name: it.product_name,
          unit_price: it.unit_price,
          quantity: it.quantity,
        })),
        shipping_address: address,
        payment_method: cardSimulation === 'fail' ? 'card_simulate_decline' : 'sandbox_credit_card',
      };

      const res = await apiClient.post('/api/v1/orders', orderPayload);
      const order = res.data;
      setCreatedOrderId(order.id);

      // Clear the shopping cart
      await apiClient.delete('/api/v1/cart');

      // Poll Saga execution for the order
      setSagaStatus('RESERVING_INVENTORY');
      pollSagaProgress(order.id);
    } catch (err: any) {
      setOrderError(err.response?.data?.detail || 'Failed to place order');
      setSubmitting(false);
      setSagaStatus(null);
    }
  };

  const pollSagaProgress = async (orderId: string) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const res = await apiClient.get(`/api/v1/orders/${orderId}`);
        const order = res.data;

        if (order.status === 'CONFIRMED' || order.status === 'SHIPPED') {
          clearInterval(interval);
          setSagaStatus('COMPLETED');
          setTimeout(() => navigate(`/orders/${orderId}`), 1800);
        } else if (order.status === 'CANCELLED') {
          clearInterval(interval);
          setSagaStatus('FAILED');
          setOrderError(`Order cancelled: ${order.cancellation_reason || 'Inventory or Payment failure'}`);
        } else if (order.status === 'AWAITING_PAYMENT') {
          setSagaStatus('PROCESSING_PAYMENT');
        }

        if (attempts > 20) {
          clearInterval(interval);
          navigate(`/orders/${orderId}`);
        }
      } catch (err) {
        console.error(err);
      }
    }, 1500);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 mb-8">Checkout</h1>

      {orderError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl flex items-center gap-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{orderError}</span>
        </div>
      )}

      {/* Real-time Saga Tracker Banner during submission */}
      {sagaStatus && (
        <div className="mb-8 p-6 bg-white border border-emerald-200 rounded-2xl shadow-sm">
          <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Loader2 className={`w-5 h-5 ${sagaStatus === 'COMPLETED' ? 'text-emerald-600' : 'animate-spin text-emerald-600'}`} />
            Distributed Saga Workflow Status
          </h3>

          <div className="grid grid-cols-4 gap-2 text-center text-xs font-semibold">
            <div className={`p-2 rounded-lg ${sagaStatus !== null ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-400'}`}>
              1. Order Created
            </div>
            <div className={`p-2 rounded-lg ${['PROCESSING_PAYMENT', 'COMPLETED'].includes(sagaStatus) ? 'bg-emerald-100 text-emerald-800' : (sagaStatus === 'RESERVING_INVENTORY' ? 'bg-amber-100 text-amber-800 animate-pulse' : 'bg-gray-100 text-gray-400')}`}>
              2. Reserve Stock
            </div>
            <div className={`p-2 rounded-lg ${sagaStatus === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : (sagaStatus === 'PROCESSING_PAYMENT' ? 'bg-amber-100 text-amber-800 animate-pulse' : 'bg-gray-100 text-gray-400')}`}>
              3. Process Payment
            </div>
            <div className={`p-2 rounded-lg ${sagaStatus === 'COMPLETED' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-400'}`}>
              4. Confirmed & Shipped
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handlePlaceOrder} className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Shipping Address */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-bold text-gray-900 border-b border-gray-100 pb-3">Shipping Address</h2>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Street Address</label>
            <input
              type="text"
              required
              value={address.street}
              onChange={(e) => setAddress({ ...address, street: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">City</label>
              <input
                type="text"
                required
                value={address.city}
                onChange={(e) => setAddress({ ...address, city: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">State</label>
              <input
                type="text"
                required
                value={address.state}
                onChange={(e) => setAddress({ ...address, state: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Postal Code</label>
              <input
                type="text"
                required
                value={address.postal_code}
                onChange={(e) => setAddress({ ...address, postal_code: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Country</label>
              <input
                type="text"
                required
                value={address.country}
                onChange={(e) => setAddress({ ...address, country: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Payment Simulation & Summary */}
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-bold text-gray-900 border-b border-gray-100 pb-3 flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-emerald-600" />
              Sandbox Payment Gateway
            </h2>

            <div className="space-y-2">
              <label className="block text-xs font-semibold text-gray-600">Simulated Card Outcome</label>
              <div className="flex gap-3">
                <label className="flex items-center gap-2 text-sm border p-3 rounded-lg flex-1 cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="cardSim"
                    checked={cardSimulation === 'success'}
                    onChange={() => setCardSimulation('success')}
                    className="text-emerald-600 focus:ring-emerald-500"
                  />
                  <div>
                    <span className="font-semibold text-gray-900 block">Approve Payment</span>
                    <span className="text-xs text-gray-500">Card ending 4242</span>
                  </div>
                </label>

                <label className="flex items-center gap-2 text-sm border p-3 rounded-lg flex-1 cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="cardSim"
                    checked={cardSimulation === 'fail'}
                    onChange={() => setCardSimulation('fail')}
                    className="text-red-600 focus:ring-red-500"
                  />
                  <div>
                    <span className="font-semibold text-gray-900 block">Decline Payment</span>
                    <span className="text-xs text-gray-500">Test compensation flow</span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <div className="flex justify-between items-center text-lg font-bold text-gray-900 mb-6">
              <span>Total Payable</span>
              <span>${cart ? (cart.total_amount / 100).toFixed(2) : '0.00'}</span>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl shadow transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Executing Saga Orchestration...
                </>
              ) : (
                <>
                  <span>Place Order & Pay</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
