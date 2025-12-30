import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FileText, 
  Building2, 
  ClipboardList, 
  Upload, 
  CheckSquare,
  Settings,
  Sliders,
  BarChart3,
  AlertTriangle,
  Sparkles
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

  const settingsItems = [
    { to: '/settings/validation-rules', icon: Sliders, label: 'Validation Rules' },
  ];

  const NavItem = ({ item }) => {
    const Icon = item.icon;
    return (
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isActive
              ? 'bg-slate-200 text-slate-900'
              : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
          }`
        }
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        <span>{item.label}</span>
      </NavLink>
    );
  };

  return (
    <aside className="fixed top-0 left-0 h-screen w-64 bg-slate-50 border-r border-slate-200 flex flex-col z-50">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-600 rounded-lg flex items-center justify-center">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-slate-900">Invoice POC</span>
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
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
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
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Actions
          </div>
          <div className="space-y-1">
            {actionItems.map((item) => (
              <NavItem key={item.to} item={item} />
            ))}
          </div>
        </div>

        {/* Settings Section */}
        <div>
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Settings
          </div>
          <div className="space-y-1">
            {settingsItems.map((item) => (
              <NavItem key={item.to} item={item} />
            ))}
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-slate-200">
        <div className="text-xs text-slate-500">
          <div className="font-medium mb-1">Backend</div>
          <code className="text-[10px] text-slate-400 break-all">
            {import.meta.env.VITE_BACKEND_URL || "Not configured"}
          </code>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
