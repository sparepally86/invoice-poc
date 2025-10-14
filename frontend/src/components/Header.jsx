import React from 'react';
import { useLocation } from 'react-router-dom';

const Header = () => {
  const location = useLocation();
  
  const getPageTitle = () => {
    const pathMap = {
      '/': 'Dashboard',
      '/invoices': 'Invoices',
      '/vendors': 'Vendors',
      '/pos': 'Purchase Orders',
      '/submit': 'Submit Invoice',
      '/tasks': 'Tasks (HITL)'
    };
    
    return pathMap[location.pathname] || 'Invoice POC';
  };

  return (
    <header className="header">
      <h1 className="header-title">{getPageTitle()}</h1>
      
      <div className="header-actions">
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '12px',
          padding: '8px 16px',
          background: 'var(--secondary-100)',
          borderRadius: '8px',
          fontSize: '14px',
          color: 'var(--secondary-600)'
        }}>
          <div style={{ 
            width: '8px', 
            height: '8px', 
            background: 'var(--success-500)', 
            borderRadius: '50%' 
          }}></div>
          System Online
        </div>
      </div>
    </header>
  );
};

export default Header;