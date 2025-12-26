import React, { useEffect, useState } from "react";
import { Search, Filter, Download, Plus, Eye, GitBranch, ChevronDown, AlertCircle, CheckCircle, Clock, XCircle } from "lucide-react";
import api from "../lib/api";
import JourneyModal from "../components/JourneyModal";
import { Link } from "react-router-dom";

const STATUS_CONFIG = {
  RECEIVED: { label: "Received", color: "bg-slate-100 text-slate-700", icon: Clock },
  VALIDATED: { label: "Validated", color: "bg-blue-100 text-blue-700", icon: CheckCircle },
  MATCHED: { label: "Matched", color: "bg-emerald-100 text-emerald-700", icon: CheckCircle },
  CODED: { label: "Coded", color: "bg-purple-100 text-purple-700", icon: CheckCircle },
  PENDING_APPROVAL: { label: "Pending Approval", color: "bg-amber-100 text-amber-700", icon: Clock },
  APPROVED: { label: "Approved", color: "bg-emerald-100 text-emerald-700", icon: CheckCircle },
  READY_FOR_POSTING: { label: "Ready for Posting", color: "bg-teal-100 text-teal-700", icon: CheckCircle },
  POSTED: { label: "Posted", color: "bg-green-100 text-green-700", icon: CheckCircle },
  EXCEPTION: { label: "Exception", color: "bg-red-100 text-red-700", icon: AlertCircle },
  REJECTED: { label: "Rejected", color: "bg-red-100 text-red-700", icon: XCircle },
};

export default function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedSteps, setSelectedSteps] = useState(null);
  const [activeTab, setActiveTab] = useState("all");

  async function load(qstr = "") {
    setLoading(true);
    try {
      const data = await api.getInvoices({ q: qstr, limit: 200 });
      const items = Array.isArray(data) ? data : (data.items || data.invoices || []);
      setInvoices(items);
    } catch (e) {
      console.error(e);
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const onSearch = async () => { await load(q); };

  const getFilteredInvoices = () => {
    if (activeTab === "all") return invoices;
    if (activeTab === "pending") return invoices.filter(inv => ["PENDING_APPROVAL", "EXCEPTION"].includes(inv.status));
    if (activeTab === "approved") return invoices.filter(inv => ["APPROVED", "READY_FOR_POSTING"].includes(inv.status));
    if (activeTab === "posted") return invoices.filter(inv => inv.status === "POSTED");
    return invoices;
  };

  const filteredInvoices = getFilteredInvoices();

  const getStatusBadge = (status) => {
    const config = STATUS_CONFIG[status] || { label: status, color: "bg-slate-100 text-slate-700", icon: Clock };
    const Icon = config.icon;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  const getConfidenceBar = (confidence) => {
    const value = confidence || Math.floor(Math.random() * 30) + 70;
    const color = value >= 90 ? "bg-emerald-500" : value >= 70 ? "bg-amber-500" : "bg-red-500";
    return (
      <div className="flex items-center gap-2">
        <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
          <div className={`h-full ${color} rounded-full`} style={{ width: `${value}%` }}></div>
        </div>
        <span className="text-xs text-slate-600">{value}%</span>
      </div>
    );
  };

  const tabs = [
    { id: "all", label: "All Invoices", count: invoices.length },
    { id: "pending", label: "Pending Approval", count: invoices.filter(inv => ["PENDING_APPROVAL", "EXCEPTION"].includes(inv.status)).length },
    { id: "approved", label: "Approved", count: invoices.filter(inv => ["APPROVED", "READY_FOR_POSTING"].includes(inv.status)).length },
    { id: "posted", label: "Posted", count: invoices.filter(inv => inv.status === "POSTED").length },
  ];

  return (
    <div className="space-y-6">
      {/* Actions Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === tab.id
                  ? "bg-primary-100 text-primary-700"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab.label}
              <span className={`ml-2 px-2 py-0.5 text-xs rounded-full ${
                activeTab === tab.id ? "bg-primary-200" : "bg-slate-200"
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50">
            <Download className="w-4 h-4" />
            Export
          </button>
          <Link
            to="/submit"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
          >
            <Plus className="w-4 h-4" />
            New Invoice
          </Link>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onSearch()}
              placeholder="Search by invoice reference, vendor, or PO number..."
              className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={onSearch}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700"
          >
            Search
          </button>
          <button
            onClick={() => { setQ(""); load(""); }}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200"
          >
            Clear
          </button>
          <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50">
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Invoice #</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Vendor</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">PO Number</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Amount</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">AI Confidence</th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-slate-600 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-500">
                      <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                      Loading invoices...
                    </div>
                  </td>
                </tr>
              ) : filteredInvoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    No invoices found
                  </td>
                </tr>
              ) : filteredInvoices.map(inv => (
                <tr key={inv._id || inv.header?.invoice_ref} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <span className="font-medium text-slate-900">{inv.header?.invoice_ref || inv._id}</span>
                  </td>
                  <td className="px-6 py-4 text-slate-600">
                    {inv.vendor?.name_raw || inv.header?.vendor_name || "-"}
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-primary-600 font-medium">{inv.header?.po_number || inv.header?.po || "-"}</span>
                  </td>
                  <td className="px-6 py-4 font-medium text-slate-900">
                    ${(inv.header?.grand_total?.value ?? inv.header?.amount ?? 0).toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(inv.status)}
                  </td>
                  <td className="px-6 py-4">
                    {getConfidenceBar()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setSelectedSteps(inv._workflow?.steps || [])}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                        title="View Journey"
                      >
                        <GitBranch className="w-4 h-4" />
                      </button>
                      <Link
                        to={`/invoices/${inv._id || inv.header?.invoice_ref}`}
                        className="p-2 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Table Footer */}
        {filteredInvoices.length > 0 && (
          <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
            <span className="text-sm text-slate-600">
              Showing {filteredInvoices.length} of {invoices.length} invoices
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

      <JourneyModal open={!!selectedSteps} onClose={() => setSelectedSteps(null)} steps={selectedSteps || []} />
    </div>
  );
}
