import React, { useEffect, useState } from "react";
import { FileText, Clock, CheckCircle, ClipboardList, TrendingUp, TrendingDown, BarChart3, Activity } from "lucide-react";
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
        
        try {
          const data = await api.getInvoices({ limit: 200 });
          const tasks = await api.getTasks();
          
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
            console.warn("MongoDB unavailable, showing demo data");
            if (!cancelled) {
              setStats({ invoices: 12, pending: 3, approved: 8, tasks: 2 });
              setIsDemoData(true);
            }
          }
        } catch (apiError) {
          console.warn("API error, showing demo data:", apiError.message);
          if (!cancelled) {
            setStats({ invoices: 12, pending: 3, approved: 8, tasks: 2 });
            setIsDemoData(true);
          }
        }
        
      } catch (err) {
        console.error("Home load error", err);
        if (!cancelled) {
          setStats({ invoices: 12, pending: 3, approved: 8, tasks: 2 });
          setIsDemoData(true);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  const StatCard = ({ icon: Icon, label, value, trend, trendLabel, iconBg, iconColor }) => (
    <div className="bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-slate-600">{label}</span>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${iconBg}`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
      </div>
      <div className="text-3xl font-bold text-slate-900 mb-2">
        {loading ? <span className="text-slate-300">...</span> : value}
      </div>
      {trend && (
        <div className="flex items-center gap-1 text-sm">
          {trend > 0 ? (
            <TrendingUp className="w-4 h-4 text-emerald-500" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-500" />
          )}
          <span className={trend > 0 ? "text-emerald-600" : "text-red-600"}>
            {trend > 0 ? "+" : ""}{trend}%
          </span>
          <span className="text-slate-500">{trendLabel}</span>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {isDemoData && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-center gap-3">
          <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
          <span className="text-sm text-amber-800">
            <strong>Demo Mode:</strong> Database connection unavailable. Showing sample data.
          </span>
        </div>
      )}
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={FileText}
          label="Total Invoices"
          value={stats.invoices}
          trend={12.5}
          trendLabel="from last month"
          iconBg="bg-primary-100"
          iconColor="text-primary-600"
        />
        <StatCard
          icon={Clock}
          label="Pending Review"
          value={stats.pending}
          trend={-8.1}
          trendLabel="vs last week"
          iconBg="bg-amber-100"
          iconColor="text-amber-600"
        />
        <StatCard
          icon={CheckCircle}
          label="Approved / Posted"
          value={stats.approved}
          trend={5.2}
          trendLabel="improvement"
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
        />
        <StatCard
          icon={ClipboardList}
          label="Open Tasks"
          value={stats.tasks}
          trend={null}
          trendLabel=""
          iconBg="bg-purple-100"
          iconColor="text-purple-600"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-slate-900">Invoice Volume Trend</h3>
          </div>
          <div className="h-48 flex items-end justify-between gap-2 px-4">
            {[40, 65, 45, 80, 55, 90, 70, 85, 60, 95, 75, 100].map((height, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2">
                <div 
                  className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600"
                  style={{ height: `${height}%` }}
                ></div>
                <span className="text-xs text-slate-400">
                  {['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'][i]}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Activity className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-slate-900">Processing Status</h3>
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">Auto-Matched</span>
                <span className="font-medium text-slate-900">89%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: '89%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">Manual Review</span>
                <span className="font-medium text-slate-900">8%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-amber-500 rounded-full" style={{ width: '8%' }}></div>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-600">Exceptions</span>
                <span className="font-medium text-slate-900">3%</span>
              </div>
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-red-500 rounded-full" style={{ width: '3%' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h3 className="font-semibold text-slate-900 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="/invoices" className="flex items-center gap-3 p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200">
            <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <div className="font-medium text-slate-900">View Invoices</div>
              <div className="text-sm text-slate-500">Manage all invoices</div>
            </div>
          </a>
          <a href="/submit" className="flex items-center gap-3 p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-emerald-600" />
            </div>
            <div>
              <div className="font-medium text-slate-900">Submit Invoice</div>
              <div className="text-sm text-slate-500">Upload new invoices</div>
            </div>
          </a>
          <a href="/tasks" className="flex items-center gap-3 p-4 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <ClipboardList className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <div className="font-medium text-slate-900">Review Tasks</div>
              <div className="text-sm text-slate-500">Handle pending tasks</div>
            </div>
          </a>
        </div>
      </div>
    </div>
  );
}
