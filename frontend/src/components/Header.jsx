import React from 'react';
import { useLocation } from 'react-router-dom';
import { Search, Bell, Moon, User } from 'lucide-react';

const Header = () => {
  const location = useLocation();
  
  const getPageInfo = () => {
    const pathMap = {
      '/': { title: 'Dashboard', subtitle: 'Overview of your accounts payable operations' },
      '/invoices': { title: 'Invoices', subtitle: 'Manage and process all invoices' },
      '/vendors': { title: 'Suppliers', subtitle: 'Manage your supplier relationships' },
      '/pos': { title: 'Purchase Orders', subtitle: 'View and manage purchase orders' },
      '/submit': { title: 'Submit Invoice', subtitle: 'Upload new invoices for processing' },
      '/tasks': { title: 'Tasks', subtitle: 'Human-in-the-loop validation tasks' }
    };
    
    // Handle dynamic routes like /invoices/:id
    if (location.pathname.startsWith('/invoices/') && location.pathname !== '/invoices') {
      return { title: 'Invoice Details', subtitle: 'View invoice information and status' };
    }
    
    return pathMap[location.pathname] || { title: 'Invoice POC', subtitle: '' };
  };

  const pageInfo = getPageInfo();

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200">
      <div className="flex items-center justify-between h-16 px-6">
        {/* Left side - Page title (hidden on mobile, shown on larger screens) */}
        <div className="hidden md:block" />

        {/* Center - Search bar */}
        <div className="flex-1 max-w-xl mx-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search invoices, vendors, PO numbers..."
              className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder:text-slate-400"
            />
          </div>
        </div>

        {/* Right side - Actions */}
        <div className="flex items-center gap-2">
          <button className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
            <Moon className="w-5 h-5" />
          </button>
          <button className="relative p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>
          <div className="ml-2 flex items-center gap-3 pl-4 border-l border-slate-200">
            <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <div className="hidden sm:block text-right">
              <div className="text-sm font-medium text-slate-700">User</div>
              <div className="text-xs text-slate-500">user@example.com</div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
