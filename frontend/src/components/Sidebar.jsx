import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FileText, 
  Building2, 
  ClipboardList, 
  Upload, 
  CheckSquare
} from 'lucide-react';

const Sidebar = () => {
  const mainNavItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/invoices', icon: FileText, label: 'Invoices' },
    { to: '/tasks', icon: CheckSquare, label: 'Tasks' },
  ];

  const masterDataItems = [
    { to: '/vendors', icon: Building2, label: 'Suppliers' },
    { to: '/pos', icon: ClipboardList, label: 'Purchase Orders' },
  ];

  const actionItems = [
    { to: '/submit', icon: Upload, label: 'Submit Invoice' },
  ];

  const NavItem = ({ item }) => {
    const Icon = item.icon;
    return (
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isActive
              ? 'bg-white/15 text-white'
              : 'text-white/70 hover:bg-white/10 hover:text-white'
          }`
        }
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        <span>{item.label}</span>
      </NavLink>
    );
  };

  return (
    <aside className="fixed top-0 left-0 h-screen w-64 bg-gradient-to-b from-slate-800 to-slate-900 flex flex-col z-50">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-500 rounded-lg flex items-center justify-center">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-white">Invoice POC</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
        {/* Main Navigation */}
        <div className="space-y-1">
          {mainNavItems.map((item) => (
            <NavItem key={item.to} item={item} />
          ))}
        </div>

        {/* Master Data Section */}
        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-white/40 uppercase tracking-wider">
            Master Data
          </div>
          <div className="space-y-1">
            {masterDataItems.map((item) => (
              <NavItem key={item.to} item={item} />
            ))}
          </div>
        </div>

        {/* Actions Section */}
        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-white/40 uppercase tracking-wider">
            Actions
          </div>
          <div className="space-y-1">
            {actionItems.map((item) => (
              <NavItem key={item.to} item={item} />
            ))}
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-white/10">
        <div className="text-xs text-white/50">
          <div className="font-medium mb-1">Backend</div>
          <code className="text-[10px] text-white/40 break-all">
            {import.meta.env.VITE_BACKEND_URL || "Not configured"}
          </code>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
