// frontend/src/api.js

const API_BASE = import.meta.env.VITE_AGENT_URL || "http://127.0.0.1:8715";

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
  const data = isJson ? await res.json().catch(() => ({})) : await res.text().catch(() => "");

  if (!res.ok) {
    const msg =
      typeof data === "string"
        ? data
        : data?.detail || data?.error || JSON.stringify(data);
    throw new Error(msg || `Request failed: ${res.status}`);
  }

  return data;
}

// ✅ shared normalizer for BOTH /workspace and /agent/launch
function normalizeWorkspacePayload(payload) {
  return {
    company_name: payload.company_name ?? payload.companyName ?? "",
    offering:
      typeof payload.offering === "string" ? { text: payload.offering } : payload.offering,
    icp: typeof payload.icp === "string" ? { text: payload.icp } : payload.icp,
  };
}

export const api = {
  baseUrl: API_BASE,

  health: () => httpJson("/health"),
  ollamaStatus: () => httpJson("/ollama/status"),

  // canonical
  createWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(normalizeWorkspacePayload(payload)),
    }),

  // ✅ back-compat (fixes “api.saveWorkspace is not a function”)
  saveWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(normalizeWorkspacePayload(payload)),
    }),

  // ✅ NEW: fixes 422 by sending dicts
  launchAgent: (payload) =>
    httpJson("/agent/launch", {
      method: "POST",
      body: JSON.stringify(normalizeWorkspacePayload(payload)),
    }),

  generateCampaign: (prompt) =>
    httpJson(`/campaign/generate?prompt=${encodeURIComponent(prompt)}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  m365Status: () => httpJson("/m365/status"),
  m365DeviceStart: () => httpJson("/m365/device/start", { method: "POST", body: JSON.stringify({}) }),
  m365DeviceComplete: () => httpJson("/m365/device/complete", { method: "POST", body: JSON.stringify({}) }),
  m365Scopes: () => httpJson("/m365/scopes"),
};

// named exports
export const saveWorkspace = (payload) => api.saveWorkspace(payload);
export const createWorkspace = (payload) => api.createWorkspace(payload);
export const launchAgent = (payload) => api.launchAgent(payload);

export default api;
