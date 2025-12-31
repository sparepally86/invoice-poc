import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";

export default function App() {
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
    
    if (location.pathname.startsWith('/invoices/') && location.pathname !== '/invoices') {
      return { title: 'Invoice Details', subtitle: 'View invoice information and status' };
    }
    
    return pathMap[location.pathname] || { title: 'Invoice POC', subtitle: '' };
  };

  const pageInfo = getPageInfo();

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />
      
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />
        
        <main className="flex-1 p-6">
          {/* Page Header */}
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-slate-900">{pageInfo.title}</h1>
            {pageInfo.subtitle && (
              <p className="mt-1 text-sm text-slate-500">{pageInfo.subtitle}</p>
            )}
          </div>
          
          {/* Page Content */}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
