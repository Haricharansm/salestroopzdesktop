import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_AGENT_URL || "http://127.0.0.1:8000";

export default function M365Connect() {
  const [status, setStatus] = useState({ loading: true });
  const [flow, setFlow] = useState(null);
  const [error, setError] = useState("");

  const refreshStatus = async () => {
    try {
      setError("");
      const res = await fetch(`${API_BASE}/m365/status`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || "Failed to fetch M365 status");
      setStatus({ loading: false, ...data });
    } catch (e) {
      setStatus({ loading: false, connected: false, configured: false });
      setError("Agent not reachable. Is FastAPI running on 127.0.0.1:8000?");
    }
  };

  useEffect(() => {
    refreshStatus();
  }, []);

  const startConnect = async () => {
    try {
      setError("");
      const res = await fetch(`${API_BASE}/m365/device/start`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Failed to start device flow");
      setFlow(data);
      // Keep status fresh (shows configured/cache flags)
      await refreshStatus();
    } catch (e) {
      setError(e.message);
    }
  };

  const completeConnect = async () => {
    try {
      setError("");
      const res = await fetch(`${API_BASE}/m365/device/complete`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Failed to complete device flow");
      setFlow(null);
      await refreshStatus();
    } catch (e) {
      setError(e.message);
    }
  };

  const configured = Boolean(status.configured);
  const connected = Boolean(status.connected);
  const hasCachedAccount = Boolean(status.has_cached_account);

  return (
    <div className="card">
      <h2>Microsoft 365 Integration</h2>
      <p>Connect Outlook mailbox to send campaigns</p>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {status.loading ? (
        <p>Checking connection...</p>
      ) : !configured ? (
        <div>
          <p style={{ color: "crimson" }}>
            Not configured. Set <code>M365_CLIENT_ID</code> in <code>agent/.env</code> and restart the backend.
          </p>

          {/* Helpful backend-provided error */}
          {status.error && <p style={{ opacity: 0.8 }}>{status.error}</p>}

          <button onClick={refreshStatus}>Refresh</button>
        </div>
      ) : connected ? (
        <div>
          <p style={{ color: "green" }}>
            Connected: {status.user?.displayName} ({status.user?.mail})
          </p>

          <div style={{ fontSize: 12, opacity: 0.8, marginTop: 8 }}>
            <div>Tenant: {status.tenant_id}</div>
            <div>Token cache: {status.token_cache_exists ? "✅ present" : "❌ missing"}</div>
          </div>

          <button onClick={refreshStatus} style={{ marginTop: 10 }}>
            Refresh
          </button>
        </div>
      ) : (
        <div>
          {/* Status diagnostics when not connected */}
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 10 }}>
            <div>Configured: ✅</div>
            <div>Cached account: {hasCachedAccount ? "✅" : "❌"}</div>
            <div>Token cache: {status.token_cache_exists ? "✅ present" : "❌ missing"}</div>
            <div>Tenant: {status.tenant_id}</div>
          </div>

          {/* Backend-provided status.error (e.g., silent token failed, /me failed) */}
          {status.error && (
            <p style={{ color: "#a15c00", whiteSpace: "pre-wrap" }}>
              {status.error}
            </p>
          )}

          {!flow ? (
            <button onClick={startConnect}>Connect Microsoft 365</button>
          ) : (
            <div style={{ marginTop: 12 }}>
              <p>
                <b>Step 1:</b> Open this link and enter the code:
              </p>
              <p>
                <a href={flow.verification_uri} target="_blank" rel="noreferrer">
                  {flow.verification_uri}
                </a>
              </p>
              <h3 style={{ letterSpacing: 2 }}>{flow.user_code}</h3>
              <p style={{ opacity: 0.8, whiteSpace: "pre-wrap" }}>{flow.message}</p>

              <p>
                <b>Step 2:</b> After you complete sign-in, click:
              </p>
              <button onClick={completeConnect}>I’ve signed in</button>
            </div>
          )}

          <button onClick={refreshStatus} style={{ marginTop: 10 }}>
            Refresh
          </button>
        </div>
      )}
    </div>
  );
}
