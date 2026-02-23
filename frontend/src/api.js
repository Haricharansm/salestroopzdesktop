// frontend/src/api.js

const API_BASE = import.meta.env.VITE_AGENT_URL || "http://127.0.0.1:8715";

/*
-----------------------------------------------------
Generic HTTP helper
-----------------------------------------------------
*/
async function httpJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  const data = isJson
    ? await res.json().catch(() => ({}))
    : await res.text().catch(() => "");

  if (!res.ok) {
    const msg =
      typeof data === "string"
        ? data
        : data?.detail || data?.error || JSON.stringify(data);

    throw new Error(msg || `Request failed: ${res.status}`);
  }

  return data;
}

/*
-----------------------------------------------------
Payload normalizer (IMPORTANT FIX)
Backend expects:

offering: { text: "..." }
icp: { text: "..." }
-----------------------------------------------------
*/
function normalizeWorkspacePayload(payload) {
  return {
    company_name: payload.company_name || payload.companyName,

    offering:
      typeof payload.offering === "string"
        ? { text: payload.offering }
        : payload.offering,

    icp:
      typeof payload.icp === "string"
        ? { text: payload.icp }
        : payload.icp,
  };
}

/*
-----------------------------------------------------
Canonical API surface
-----------------------------------------------------
*/
export const api = {
  baseUrl: API_BASE,

  // --- agent core ---
  health: () => httpJson("/health"),
  ollamaStatus: () => httpJson("/ollama/status"),

  createWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(normalizeWorkspacePayload(payload)),
    }),

  generateCampaign: (prompt) =>
    httpJson(`/campaign/generate?prompt=${encodeURIComponent(prompt)}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  // --- Microsoft 365 ---
  m365Status: () => httpJson("/m365/status"),

  m365DeviceStart: () =>
    httpJson("/m365/device/start", {
      method: "POST",
      body: JSON.stringify({}),
    }),

  m365DeviceComplete: () =>
    httpJson("/m365/device/complete", {
      method: "POST",
      body: JSON.stringify({}),
    }),

  // --- debug ---
  m365Scopes: () => httpJson("/m365/scopes"),
};

/*
-----------------------------------------------------
Back-compat named exports
-----------------------------------------------------
*/
export const createWorkspace = (payload) => api.createWorkspace(payload);
export const generateCampaign = (prompt) => api.generateCampaign(prompt);
export const m365Status = () => api.m365Status();
export const m365DeviceStart = () => api.m365DeviceStart();
export const m365DeviceComplete = () => api.m365DeviceComplete();
export const ollamaStatus = () => api.ollamaStatus();
export const health = () => api.health();

export default api;
