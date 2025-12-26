import React, { useEffect, useState } from "react";
import { Search, Filter, Download, Plus, ChevronDown, ChevronRight, ClipboardList, Building2, DollarSign, AlertCircle, CheckCircle, Clock } from "lucide-react";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function POs() {
  const [pos, setPos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openMap, setOpenMap] = useState({});
  const [err, setErr] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const resp = await fetch(`${BACKEND}/api/v1/pos`);
        const data = await resp.json();
        const items = Array.isArray(data) ? data : (data.pos || data.items || []);
        if (!cancelled) setPos(items);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  function toggle(poNumber) {
    setOpenMap((m) => ({ ...m, [poNumber]: !m[poNumber] }));
  }

  const filteredPOs = pos.filter(p => {
    const poNumber = p.po_number || p._id || p.number || "";
    const vendor = p.vendor_name || p.vendor || "";
    const query = searchQuery.toLowerCase();
    return poNumber.toLowerCase().includes(query) || vendor.toLowerCase().includes(query);
  });

  const getStatusBadge = (status) => {
    const statusConfig = {
      open: { label: "Open", color: "bg-emerald-100 text-emerald-700", icon: CheckCircle },
      closed: { label: "Closed", color: "bg-slate-100 text-slate-700", icon: Clock },
      pending: { label: "Pending", color: "bg-amber-100 text-amber-700", icon: Clock },
    };
    const config = statusConfig[status?.toLowerCase()] || { label: status || "Open", color: "bg-emerald-100 text-emerald-700", icon: CheckCircle };
    const Icon = config.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search purchase orders..."
              className="pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent w-72"
            />
          </div>
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50">
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700">
            <Plus className="w-4 h-4" />
            New PO
          </button>
        </div>
      </div>

      {/* Error State */}
      {err && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-sm text-red-700">Error loading purchase orders: {err}</span>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-12">
          <div className="flex items-center justify-center gap-2 text-slate-500">
            <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            Loading purchase orders...
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredPOs.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center text-slate-500">
          {searchQuery ? "No purchase orders match your search" : "No purchase orders found"}
        </div>
      )}

      {/* PO Cards */}
      {!loading && filteredPOs.length > 0 && (
        <div className="space-y-4">
          {filteredPOs.map((p, idx) => {
            const poNumber = p.po_number || p._id || p.number || `PO-${idx+1}`;
            const open = !!openMap[poNumber];
            const lines = p.lines || p.items || [];
            const total = p.total || p.amount || 0;
            
            return (
              <div key={idx} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                <button
                  onClick={() => toggle(poNumber)}
                  className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
                      <ClipboardList className="w-6 h-6 text-primary-600" />
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-slate-900">{poNumber}</span>
                        {getStatusBadge(p.status)}
                      </div>
                      <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                        <span className="flex items-center gap-1.5">
                          <Building2 className="w-4 h-4" />
                          {p.vendor_name || p.vendor || "Unknown Supplier"}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <DollarSign className="w-4 h-4" />
                          ${Number(total).toLocaleString()}
                        </span>
                        <span>{lines.length} line items</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {open ? (
                      <ChevronDown className="w-5 h-5 text-slate-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-slate-400" />
                    )}
                  </div>
                </button>

                {open && lines.length > 0 && (
                  <div className="border-t border-slate-200">
                    <table className="w-full">
                      <thead>
                        <tr className="bg-slate-50">
                          <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">#</th>
                          <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Description</th>
                          <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Qty</th>
                          <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Unit Price</th>
                          <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {lines.map((ln, i) => (
                          <tr key={i} className="hover:bg-slate-50">
                            <td className="px-6 py-3 text-sm text-slate-500">{i + 1}</td>
                            <td className="px-6 py-3 text-sm text-slate-900">{ln.item_text || ln.description || ln.name || "-"}</td>
                            <td className="px-6 py-3 text-sm text-slate-600 text-right">{ln.qty ?? ln.quantity ?? "-"}</td>
                            <td className="px-6 py-3 text-sm text-slate-600 text-right">${Number(ln.unit_price ?? ln.price ?? 0).toLocaleString()}</td>
                            <td className="px-6 py-3 text-sm text-slate-900 text-right font-medium">${Number(ln.amount ?? ln.line_total ?? 0).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-slate-50 border-t border-slate-200">
                          <td colSpan={4} className="px-6 py-3 text-sm font-semibold text-slate-700 text-right">Total</td>
                          <td className="px-6 py-3 text-sm font-semibold text-slate-900 text-right">${Number(total).toLocaleString()}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}

                {open && lines.length === 0 && (
                  <div className="border-t border-slate-200 px-6 py-8 text-center text-slate-500">
                    No line items
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      {!loading && filteredPOs.length > 0 && (
        <div className="flex items-center justify-between text-sm text-slate-600">
          <span>Showing {filteredPOs.length} of {pos.length} purchase orders</span>
        </div>
      )}
    </div>
  );
}
