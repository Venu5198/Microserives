import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShoppingCart, Package, User, LogOut, ShieldAlert, Store } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Navbar: React.FC = () => {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
              <Store className="w-6 h-6 text-emerald-600" />
              <span>OmniStore</span>
            </Link>
            <div className="hidden md:flex items-center space-x-4">
              <Link to="/" className="text-gray-600 hover:text-gray-900 font-medium">
                Products
              </Link>
              {user && (
                <Link to="/orders" className="text-gray-600 hover:text-gray-900 font-medium">
                  My Orders
                </Link>
              )}
              {isAdmin && (
                <Link
                  to="/admin"
                  className="flex items-center gap-1 text-emerald-600 hover:text-emerald-700 font-semibold"
                >
                  <ShieldAlert className="w-4 h-4" />
                  Admin Console
                </Link>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Link
              to="/cart"
              className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full"
            >
              <ShoppingCart className="w-5 h-5" />
            </Link>

            {user ? (
              <div className="flex items-center gap-3">
                <Link
                  to="/profile"
                  className="flex items-center gap-1.5 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  <User className="w-4 h-4" />
                  <span className="hidden sm:inline">{user.email}</span>
                </Link>
                <button
                  onClick={handleLogout}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-gray-100 rounded-full"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="px-3 py-1.5 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-md"
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

