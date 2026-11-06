import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { ProtectedRoute } from './components/ProtectedRoute';

import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ProductList } from './pages/ProductList';
import { ProductDetail } from './pages/ProductDetail';
import { Cart } from './pages/Cart';
import { Checkout } from './pages/Checkout';
import { Orders } from './pages/Orders';
import { OrderDetail } from './pages/OrderDetail';
import { Profile } from './pages/Profile';

import { AdminDashboard } from './pages/admin/AdminDashboard';
import { AdminProducts } from './pages/admin/AdminProducts';
import { AdminInventory } from './pages/admin/AdminInventory';
import { AdminOrders } from './pages/admin/AdminOrders';
import { AdminPayments } from './pages/admin/AdminPayments';
import { AdminShipments } from './pages/admin/AdminShipments';
import { AdminNotifications } from './pages/admin/AdminNotifications';
import { AdminHealth } from './pages/admin/AdminHealth';

const queryClient = new QueryClient();

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <div className="min-h-screen bg-gray-50 flex flex-col justify-between">
            <div>
              <Navbar />
              <main>
                <Routes>
                  {/* Public Routes */}
                  <Route path="/" element={<ProductList />} />
                  <Route path="/products/:id" element={<ProductDetail />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />

                  {/* Customer Protected Routes */}
                  <Route element={<ProtectedRoute />}>
                    <Route path="/cart" element={<Cart />} />
                    <Route path="/checkout" element={<Checkout />} />
                    <Route path="/orders" element={<Orders />} />
                    <Route path="/orders/:id" element={<OrderDetail />} />
                    <Route path="/profile" element={<Profile />} />
                  </Route>

                  {/* Admin Protected Routes */}
                  <Route element={<ProtectedRoute adminOnly />}>
                    <Route path="/admin" element={<AdminDashboard />}>
                      <Route index element={<Navigate to="/admin/products" replace />} />
                      <Route path="products" element={<AdminProducts />} />
                      <Route path="inventory" element={<AdminInventory />} />
                      <Route path="orders" element={<AdminOrders />} />
                      <Route path="payments" element={<AdminPayments />} />
                      <Route path="shipments" element={<AdminShipments />} />
                      <Route path="notifications" element={<AdminNotifications />} />
                      <Route path="health" element={<AdminHealth />} />
                    </Route>
                  </Route>

                  {/* Catch-all */}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </main>
            </div>

            <footer className="bg-white border-t border-gray-200 py-6 text-center text-xs text-gray-500">
              <p>OmniStore Production E-Commerce Platform — Event-Driven Microservices Architecture</p>
            </footer>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

