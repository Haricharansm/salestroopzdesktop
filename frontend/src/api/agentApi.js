const API_BASE = import.meta.env.VITE_AGENT_API_BASE || "http://localhost:8000";

async function httpJson(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const msg = typeof data === "string" ? data : (data.detail || data.error || JSON.stringify(data));
    throw new Error(msg);
  }
  return data;
}

export async function getM365Status() {
  return httpJson("/m365/status");
}

export async function getM365Scopes() {
  return httpJson("/m365/scopes");
}

export async function startM365DeviceFlow() {
  return httpJson("/m365/device/start", { method: "POST", body: JSON.stringify({}) });
}

export async function completeM365DeviceFlow() {
  return httpJson("/m365/device/complete", { method: "POST", body: JSON.stringify({}) });
}
