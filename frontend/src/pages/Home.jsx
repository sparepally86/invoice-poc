// src/pages/Home.jsx
import React, { useEffect, useState } from "react";
import api from "../lib/api";

export default function Home() {
  const [stats, setStats] = useState({ invoices: 0, pending: 0, approved: 0, tasks: 0 });
  const [loading, setLoading] = useState(true);
  const [isDemoData, setIsDemoData] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        
        // Try to get real data from API
        try {
          const data = await api.getInvoices({ limit: 200 });
          const tasks = await api.getTasks();
          
          // Check if we got actual data (not an error response)
          if (data && !data.error && (Array.isArray(data) || data.items)) {
            const invoices = Array.isArray(data) ? data : (data.items || []);
            let s = { 
              invoices: invoices.length, 
              pending: 0, 
              approved: 0, 
              tasks: Array.isArray(tasks) && !tasks.error ? tasks.length : 0 
            };
            
            for (const inv of invoices) {
              if (inv.status === "PENDING_APPROVAL" || inv.status === "EXCEPTION") s.pending++;
              if (["APPROVED", "READY_FOR_POSTING", "POSTED"].includes(inv.status)) s.approved++;
            }
            
            if (!cancelled) setStats(s);
          } else {
            // Fallback to demo data when MongoDB is unavailable
            console.warn("MongoDB unavailable, showing demo data");
            if (!cancelled) {
              setStats({
                invoices: 12,
                pending: 3,
                approved: 8,
                tasks: 2
              });
              setIsDemoData(true);
            }
          }
        } catch (apiError) {
          console.warn("API error, showing demo data:", apiError.message);
          // Show demo data when API fails
          if (!cancelled) {
            setStats({
              invoices: 12,
              pending: 3,
              approved: 8,
              tasks: 2
            });
            setIsDemoData(true);
          }
        }
        
      } catch (err) {
        console.error("Home load error", err);
        // Final fallback
        if (!cancelled) {
          setStats({
            invoices: 12,
            pending: 3,
            approved: 8,
            tasks: 2
          });
          setIsDemoData(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  return (
    <div>
      {isDemoData && (
        <div className="alert alert-warning mb-4">
          <strong>⚠️ Demo Mode:</strong> Database connection unavailable. Showing sample data for demonstration.
        </div>
      )}
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon primary">📊</div>
          <div className="stat-label">Total Invoices</div>
          <div className="stat-value">{loading ? "…" : stats.invoices}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon warning">⏳</div>
          <div className="stat-label">Pending Review</div>
          <div className="stat-value">{loading ? "…" : stats.pending}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon success">✅</div>
          <div className="stat-label">Approved / Posted</div>
          <div className="stat-value">{loading ? "…" : stats.approved}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-icon accent">📋</div>
          <div className="stat-label">Open Tasks</div>
          <div className="stat-value">{loading ? "…" : stats.tasks}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Welcome to Invoice POC</h2>
        </div>
        <div className="card-body">
          <p style={{ 
            color: 'var(--secondary-600)', 
            fontSize: '16px',
            lineHeight: '1.6',
            margin: 0
          }}>
            This dashboard provides an overview of your invoice processing system. 
            Use the sidebar navigation to access different sections:
          </p>
          
          <div style={{ 
            marginTop: '24px',
            display: 'grid',
            gap: '12px'
          }}>
            <div style={{ 
              padding: '12px 16px',
              background: 'var(--secondary-50)',
              borderRadius: '8px',
              borderLeft: '3px solid var(--primary-500)'
            }}>
              <strong>📄 Invoices</strong> - View and manage all submitted invoices
            </div>
            <div style={{ 
              padding: '12px 16px',
              background: 'var(--secondary-50)',
              borderRadius: '8px',
              borderLeft: '3px solid var(--accent-500)'
            }}>
              <strong>📤 Submit Invoice</strong> - Upload new invoices for processing
            </div>
            <div style={{ 
              padding: '12px 16px',
              background: 'var(--secondary-50)',
              borderRadius: '8px',
              borderLeft: '3px solid var(--warning-500)'
            }}>
              <strong>✅ Tasks</strong> - Handle human-in-the-loop validation tasks
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
