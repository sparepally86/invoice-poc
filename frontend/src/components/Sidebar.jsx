import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
  const navItems = [
    { to: '/', icon: '🏠', label: 'Dashboard' },
    { to: '/invoices', icon: '📄', label: 'Invoices' },
    { to: '/vendors', icon: '🏢', label: 'Vendors' },
    { to: '/pos', icon: '📋', label: 'Purchase Orders' },
    { to: '/submit', icon: '📤', label: 'Submit Invoice' },
    { to: '/tasks', icon: '✅', label: 'Tasks (HITL)' }
  ];

  const backend = import.meta.env.VITE_BACKEND_URL || "env not set";

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🧾</div>
          <span>Invoice POC</span>
        </div>
      </div>
      
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <div key={item.to} className="nav-item">
            <NavLink
              to={item.to}
              className={({ isActive }) => 
                `nav-link ${isActive ? 'active' : ''}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          </div>
        ))}
      </nav>

      <div style={{ 
        padding: '24px', 
        borderTop: '1px solid rgba(255, 255, 255, 0.1)', 
        marginTop: 'auto',
        fontSize: '12px',
        color: 'rgba(255, 255, 255, 0.6)'
      }}>
        <div style={{ marginBottom: '8px', fontWeight: '600' }}>Backend Status</div>
        <code style={{ 
          background: 'rgba(255, 255, 255, 0.1)', 
          padding: '4px 8px', 
          borderRadius: '4px',
          color: 'rgba(255, 255, 255, 0.8)',
          fontSize: '11px',
          wordBreak: 'break-all'
        }}>
          {backend}
        </code>
      </div>
    </div>
  );
};

export default Sidebar;