// src/lib/api.js
import axios from "axios";

// Prefer VITE_API_BASE (matches ExplanationPanel), fallback to VITE_BACKEND_URL, then Render URL
const RAW_BASE = (import.meta.env.VITE_API_BASE || import.meta.env.VITE_BACKEND_URL || "").replace(/\/$/, "");
const API_BASE = RAW_BASE || "https://invoice-poc-1gpt.onrender.com";

const client = axios.create({
  baseURL: API_BASE + "/api/v1",
  timeout: 20000,
});

export default {
  getInvoices: (params = {}) => client.get("/invoices", { params }).then(r => r.data),
  getInvoice: (id) => client.get(`/invoices/${encodeURIComponent(id)}`).then(r => r.data),
  postIncoming: (payload) => client.post("/incoming", payload).then(r => r.data),
  generateInvoice: (poNumber, splitFirstLine) => client.post(`/dev/generate-invoice?po_number=${encodeURIComponent(poNumber)}${splitFirstLine ? "&split_first_line=true" : ""}`).then(r => r.data),
  getTasks: () => client.get("/tasks/pending").then(r => r.data),
  approveInvoice: (id, body) => client.post(`/invoices/${encodeURIComponent(id)}/approve`, body).then(r => r.data),
  rejectInvoice: (id, body) => client.post(`/invoices/${encodeURIComponent(id)}/reject`, body).then(r => r.data),
};
