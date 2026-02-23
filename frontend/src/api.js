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

export const api = {
  baseUrl: API_BASE,

  health: () => httpJson("/health"),
  ollamaStatus: () => httpJson("/ollama/status"),

  // backend expects STRINGS
  saveWorkspace: (payload) =>
    httpJson("/workspace", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  launchAgent: (payload) =>
    httpJson("/agent/launch", {
      method: "POST",
      body: JSON.stringify(payload),
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
};

export default api;
