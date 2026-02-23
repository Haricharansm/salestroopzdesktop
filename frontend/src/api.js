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

// IMPORTANT:
// Your backend currently behaves inconsistently:
// - /workspace seems to accept dict-like shapes (TextLike)
// - /agent/launch is currently expecting STRINGS (based on your latest 422)
// So: normalize per-endpoint.
function asString(v) {
  if (typeof v === "string") return v;
  if (v && typeof v === "object") {
    // common shapes
    if (typeof v.text === "string") return v.text;
    if (typeof v.value === "string") return v.value;
    if (typeof v.input === "string") return v.input;
    // fallback: first string field
    for (const k of Object.keys(v)) {
      if (typeof v[k] === "string") return v[k];
    }
  }
  return "";
}

function normalizeForWorkspace(payload) {
  return {
    company_name: payload.company_name ?? payload.companyName ?? "",
    // allow string OR object
    offering: payload.offering,
    icp: payload.icp,
  };
}

function normalizeForLaunch(payload) {
  // based on your latest error, Launch expects STRING values
  return {
    offering: asString(payload.offering),
    icp: asString(payload.icp),
    workspace_id: payload.workspace_id ?? null,
  };
}

export const api = {
  baseUrl: API_BASE,

  health: () => httpJson("/health"),
  ollamaStatus: () => httpJson("/ollama/status"),

  createWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(normalizeForWorkspace(payload)),
    }),

  // back-compat
  saveWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(normalizeForWorkspace(payload)),
    }),

  launchAgent: (payload) =>
    httpJson("/agent/launch", {
      method: "POST",
      body: JSON.stringify(normalizeForLaunch(payload)),
    }),

  generateCampaign: (prompt) =>
    httpJson(`/campaign/generate?prompt=${encodeURIComponent(prompt)}`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  m365Status: () => httpJson("/m365/status"),
  m365DeviceStart: () =>
    httpJson("/m365/device/start", { method: "POST", body: JSON.stringify({}) }),
  m365DeviceComplete: () =>
    httpJson("/m365/device/complete", { method: "POST", body: JSON.stringify({}) }),
  m365Scopes: () => httpJson("/m365/scopes"),
};

// ✅ Named exports (this is what your error is about)
export const createWorkspace = (payload) => api.createWorkspace(payload);
export const saveWorkspace = (payload) => api.saveWorkspace(payload);
export const launchAgent = (payload) => api.launchAgent(payload);

export default api;
