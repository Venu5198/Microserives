import React, { useEffect, useState } from 'react';
import { Layers, RefreshCw, PlusCircle, MinusCircle } from 'lucide-react';
import { apiClient } from '../../api/client';

interface InventoryItem {
  product_id: string;
  sku: string;
  available_quantity: number;
  reserved_quantity: number;
  sold_quantity: number;
  total_quantity: number;
  low_stock_threshold: number;
  updated_at: string;
}

export const AdminInventory: React.FC = () => {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [adjustItem, setAdjustItem] = useState<InventoryItem | null>(null);
  const [adjustment, setAdjustment] = useState(10);
  const [reason, setReason] = useState('Stock replenishment');

  const fetchInventory = async () => {
    try {
      const res = await apiClient.get('/api/v1/inventory');
      setInventory(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, []);

  const handleAdjust = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjustItem) return;
    try {
      await apiClient.patch(`/api/v1/inventory/${adjustItem.product_id}`, {
        adjustment: Number(adjustment),
        reason,
      });
      setAdjustItem(null);
      await fetchInventory();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to adjust stock');
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Inventory Stock & Concurrency Controls</h2>
          <p className="text-xs text-gray-500">Atomic reservations prevent overselling across parallel orders</p>
        </div>
        <button
          onClick={fetchInventory}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-xs uppercase text-gray-700 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3">Product ID</th>
                <th className="px-4 py-3">SKU</th>
                <th className="px-4 py-3">Available</th>
                <th className="px-4 py-3">Reserved (Saga Active)</th>
                <th className="px-4 py-3">Sold (Fulfilled)</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3 text-right">Adjust Stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {inventory.map((item) => (
                <tr key={item.product_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-gray-900">
                    {item.product_id}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{item.sku}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`font-bold ${
                        item.available_quantity <= item.low_stock_threshold
                          ? 'text-red-600'
                          : 'text-emerald-700'
                      }`}
                    >
                      {item.available_quantity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-amber-600 font-semibold">{item.reserved_quantity}</td>
                  <td className="px-4 py-3 text-blue-600 font-semibold">{item.sold_quantity}</td>
                  <td className="px-4 py-3 font-bold text-gray-900">{item.total_quantity}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => {
                        setAdjustItem(item);
                        setAdjustment(10);
                        setReason('Stock replenishment');
                      }}
                      className="px-2.5 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200 bg-emerald-50 rounded hover:bg-emerald-100"
                    >
                      Adjust
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Adjust Modal */}
      {adjustItem && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-xl">
            <h3 className="text-base font-bold text-gray-900 mb-2">
              Adjust Stock: {adjustItem.sku}
            </h3>
            <p className="text-xs text-gray-500 mb-4">
              Current available: <strong className="text-emerald-700">{adjustItem.available_quantity}</strong>
            </p>

            <form onSubmit={handleAdjust} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Quantity (+ to add, - to subtract)
                </label>
                <input
                  type="number"
                  required
                  value={adjustment}
                  onChange={(e) => setAdjustment(parseInt(e.target.value))}
                  className="w-full px-3 py-1.5 border rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Audit Reason</label>
                <input
                  type="text"
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-1.5 border rounded-lg text-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setAdjustItem(null)}
                  className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 bg-emerald-600 text-white font-semibold text-xs rounded-lg hover:bg-emerald-700"
                >
                  Confirm Adjustment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

