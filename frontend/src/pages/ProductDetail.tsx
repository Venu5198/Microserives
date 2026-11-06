import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ShoppingBag, ArrowLeft, Check, ShieldCheck, Truck } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { Product } from './ProductList';

export const ProductDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [added, setAdded] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    const fetchProduct = async () => {
      try {
        const res = await apiClient.get(`/api/v1/products/${id}`);
        setProduct(res.data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchProduct();
  }, [id]);

  const addToCart = async () => {
    if (!user) {
      window.location.href = '/login';
      return;
    }
    if (!product) return;
    try {
      await apiClient.post('/api/v1/cart/items', {
        product_id: product.id,
        quantity,
      });
      setAdded(true);
      setTimeout(() => setAdded(false), 2000);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add item to cart');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center">
        <h2 className="text-xl font-bold text-gray-800">Product not found</h2>
        <Link to="/" className="text-emerald-600 mt-4 inline-block hover:underline">
          Back to catalog
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <Link to="/" className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 mb-6">
        <ArrowLeft className="w-4 h-4" />
        Back to all products
      </Link>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm grid grid-cols-1 md:grid-cols-2 gap-8 p-8">
        <div className="h-96 rounded-xl overflow-hidden bg-gray-100 flex items-center justify-center">
          <img
            src={product.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&auto=format&fit=crop&q=60'}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        </div>

        <div className="flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider bg-emerald-50 px-2.5 py-1 rounded-full">
              {product.category}
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 mt-3">{product.name}</h1>
            <p className="text-xs text-gray-400 mt-1">SKU: {product.sku}</p>
            <div className="mt-4 text-3xl font-bold text-gray-900">
              ${(product.price / 100).toFixed(2)}
            </div>

            <p className="mt-4 text-sm text-gray-600 leading-relaxed">{product.description}</p>

            <div className="mt-6 flex items-center gap-4">
              <label className="text-sm font-medium text-gray-700">Quantity:</label>
              <div className="flex items-center border border-gray-300 rounded-lg">
                <button
                  type="button"
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  className="px-3 py-1 hover:bg-gray-100 text-gray-600 font-bold"
                >
                  -
                </button>
                <span className="px-4 py-1 text-sm font-semibold">{quantity}</span>
                <button
                  type="button"
                  onClick={() => setQuantity(quantity + 1)}
                  className="px-3 py-1 hover:bg-gray-100 text-gray-600 font-bold"
                >
                  +
                </button>
              </div>
            </div>
          </div>

          <div className="mt-8 space-y-4">
            <button
              onClick={addToCart}
              className={`w-full py-3 px-6 rounded-xl font-semibold flex items-center justify-center gap-2 shadow transition ${
                added
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              {added ? (
                <>
                  <Check className="w-5 h-5" /> Added to Shopping Cart
                </>
              ) : (
                <>
                  <ShoppingBag className="w-5 h-5" /> Add to Cart
                </>
              )}
            </button>

            <div className="grid grid-cols-2 gap-3 pt-4 border-t border-gray-100 text-xs text-gray-500">
              <div className="flex items-center gap-2">
                <Truck className="w-4 h-4 text-emerald-600" />
                <span>Fast 3-Day Shipping</span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>30-Day Money Back</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

