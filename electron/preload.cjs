const { contextBridge } = require("electron");

/*
Production-safe API base:
- Electron main injects SALESTROOPZ_API_PORT
- Default fallback for dev = 8715
*/
const API_PORT = process.env.SALESTROOPZ_API_PORT || "8715";
const API_BASE = `http://127.0.0.1:${API_PORT}`;

async function httpGet(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${path} failed: ${res.status} ${text}`);
  }

  return res.json();
}

async function httpPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body ?? {}),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST ${path} failed: ${res.status} ${text}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return res.json();
  return res.text();
}

contextBridge.exposeInMainWorld("salestroopz", {
  version: "0.1.0",
  apiBase: API_BASE,

  agent: {
    health: () => httpGet("/health"),
    ollamaStatus: () => httpGet("/ollama/status"),
    createWorkspace: (payload) => httpPost("/workspace", payload),

    generateCampaign: (prompt) =>
      fetch(`${API_BASE}/campaign/generate?prompt=${encodeURIComponent(prompt)}`, {
        method: "POST",
        headers: { Accept: "application/json" },
      }).then(async (res) => {
        if (!res.ok)
          throw new Error(`POST /campaign/generate failed: ${res.status}`);
        return res.json();
      }),
  },
});
