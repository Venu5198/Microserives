import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  Package,
  Layers,
  ShoppingBag,
  CreditCard,
  Truck,
  Bell,
  Activity,
  ShieldCheck,
} from 'lucide-react';

export const AdminDashboard: React.FC = () => {
  const navItems = [
    { name: 'Products', path: '/admin/products', icon: Package },
    { name: 'Inventory', path: '/admin/inventory', icon: Layers },
    { name: 'Orders', path: '/admin/orders', icon: ShoppingBag },
    { name: 'Payments', path: '/admin/payments', icon: CreditCard },
    { name: 'Shipments & Courier', path: '/admin/shipments', icon: Truck },
    { name: 'Notifications', path: '/admin/notifications', icon: Bell },
    { name: 'System Health', path: '/admin/health', icon: Activity },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-8">
        <div className="p-2.5 bg-emerald-100 rounded-xl text-emerald-700">
          <ShieldCheck className="w-7 h-7" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900">
            Admin Management Console
          </h1>
          <p className="text-sm text-gray-500">
            Orchestrate microservices, simulate couriers, monitor distributed events & stock
          </p>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Sidebar Nav */}
        <div className="w-full lg:w-64 flex-shrink-0">
          <div className="bg-white border border-gray-200 rounded-2xl p-3 shadow-sm space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-semibold transition ${
                      isActive
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}
          </div>
        </div>

        {/* Content Outlet */}
        <div className="flex-1 bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm min-h-[600px]">
          <Outlet />
        </div>
      </div>
    </div>
  );
};
