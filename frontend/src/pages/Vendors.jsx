import React, { useEffect, useState } from "react";
import { Search, Filter, Download, Plus, Building2, MapPin, Mail, Phone, MoreVertical, AlertCircle } from "lucide-react";

const BACKEND = (import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "") || "https://invoice-poc-1gpt.onrender.com";

export default function Vendors() {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const resp = await fetch(`${BACKEND}/api/v1/vendors`);
        const data = await resp.json();
        const items = Array.isArray(data) ? data : (data.vendors || data.items || []);
        if (!cancelled) setVendors(items);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => (cancelled = true);
  }, []);

  const filteredVendors = vendors.filter(v => {
    const name = v.name_raw || v.name || v.vendor_name || "";
    const id = v.vendor_id || v._id || v.vendorId || "";
    const query = searchQuery.toLowerCase();
    return name.toLowerCase().includes(query) || id.toLowerCase().includes(query);
  });

  const getStatusBadge = (status) => {
    const isActive = status === "active" || !status;
    return (
      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
        isActive ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"
      }`}>
        {isActive ? "Active" : status}
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
              placeholder="Search suppliers..."
              className="pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent w-64"
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
            Add Supplier
          </button>
        </div>
      </div>

      {/* Error State */}
      {err && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <span className="text-sm text-red-700">Error loading suppliers: {err}</span>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Supplier</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Location</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-500">
                      <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                      Loading suppliers...
                    </div>
                  </td>
                </tr>
              ) : filteredVendors.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500">
                    {searchQuery ? "No suppliers match your search" : "No suppliers found"}
                  </td>
                </tr>
              ) : filteredVendors.map((v, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                        <Building2 className="w-5 h-5 text-primary-600" />
                      </div>
                      <div>
                        <div className="font-medium text-slate-900">{v.name_raw || v.name || v.vendor_name || "-"}</div>
                        {v.email && <div className="text-xs text-slate-500">{v.email}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-mono text-sm text-slate-600">{v.vendor_id || v._id || v.vendorId || "-"}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 text-slate-600">
                      <MapPin className="w-4 h-4 text-slate-400" />
                      <span className="text-sm">{v.country || v.location || v.notes || "-"}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(v.status)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end">
                      <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        {filteredVendors.length > 0 && (
          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
            <span className="text-sm text-slate-600">
              Showing {filteredVendors.length} of {vendors.length} suppliers
            </span>
            <div className="flex items-center gap-2">
              <button className="px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-white disabled:opacity-50" disabled>
                Previous
              </button>
              <button className="px-3 py-1.5 text-sm text-slate-600 border border-slate-200 rounded-lg hover:bg-white disabled:opacity-50" disabled>
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
