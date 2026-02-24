import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

/**
 * Production RunControls
 * - Source of truth: backend campaign status
 * - Minimal UI by default: Start / Pause / Stop + status
 * - Advanced config is hidden (v1)
 */
export default function RunControls({ campaignId }) {
  const [status, setStatus] = useState("draft"); // draft | running | paused | stopped | ...
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  // Hidden-by-default config (v1)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [config, setConfig] = useState({
    dailyLimit: 80,
    concurrency: 4,
    quietHoursStart: "20:00",
    quietHoursEnd: "07:00",
    stopOnNegative: true,
    autoBookMeeting: true,
  });

  const badge = useMemo(() => {
    if (!campaignId) return { text: "NO CAMPAIGN", cls: "warn" };
    if (status === "running") return { text: "RUNNING", cls: "good" };
    if (status === "paused") return { text: "PAUSED", cls: "warn" };
    if (status === "stopped") return { text: "STOPPED", cls: "warn" };
    return { text: (status || "DRAFT").toUpperCase(), cls: "" };
  }, [campaignId, status]);

  async function refreshStatus() {
    if (!campaignId) return;
    try {
      // Requires backend GET /campaign/{id} (added below). If not available yet, we fail silently.
      const data = await fetch(`${api.baseUrl}/campaign/${campaignId}`, { method: "GET" })
        .then(async (r) => {
          const ct = r.headers.get("content-type") || "";
          const body = ct.includes("application/json") ? await r.json().catch(() => ({})) : await r.text().catch(() => "");
          if (!r.ok) throw new Error(typeof body === "string" ? body : body?.detail || "Failed to fetch campaign");
          return body;
        });

      if (data?.status) setStatus(data.status);
    } catch {
      // If endpoint isn't present yet, leave status as-is.
    }
  }

  useEffect(() => {
    setMsg("");
    if (!campaignId) setStatus("draft");
    if (campaignId) refreshStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const start = async () => {
    if (!campaignId) {
      setMsg("⚠️ Launch a campaign first.");
      return;
    }

    try {
      setLoading(true);
      setMsg("");

      const data = await fetch(`${api.baseUrl}/campaign/${campaignId}/start`, {
        method: "POST",
      }).then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body?.detail || "Failed to start campaign");
        return body;
      });

      setStatus(data?.status || "running");
      setMsg("✅ Campaign started.");
    } catch (e) {
      setMsg(`❌ ${e?.message || String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const pause = async () => {
    if (!campaignId) return;

    try {
      setLoading(true);
      setMsg("");

      const data = await fetch(`${api.baseUrl}/campaign/${campaignId}/pause`, {
        method: "POST",
      }).then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body?.detail || "Failed to pause campaign");
        return body;
      });

      setStatus(data?.status || "paused");
      setMsg("⏸️ Campaign paused.");
    } catch (e) {
      setMsg(`❌ ${e?.message || String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const stop = async () => {
    // v1 behavior: if you add /stop later, call it. For now we map Stop -> paused.
    if (!campaignId) return;

    try {
      setLoading(true);
      setMsg("");

      const data = await fetch(`${api.baseUrl}/campaign/${campaignId}/pause`, {
        method: "POST",
      }).then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body?.detail || "Failed to stop campaign");
        return body;
      });

      setStatus(data?.status || "paused");
      setMsg("🛑 Campaign stopped (paused).");
    } catch (e) {
      setMsg(`❌ ${e?.message || String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const canStart = campaignId && status !== "running";
  const canPause = campaignId && status === "running";
  const canStop = campaignId && status !== "draft";

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginBottom: 0 }}>Campaign Controls</h2>
        <span className={`badge ${badge.cls}`}>{badge.text}</span>
      </div>

      {!campaignId ? (
        <p style={{ marginTop: 8, opacity: 0.85 }}>
          Launch a campaign first. Then you can start or pause it from here.
        </p>
      ) : null}

      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn primary" onClick={start} disabled={loading || !canStart}>
          {loading && canStart ? "Starting..." : "Start"}
        </button>
        <button className="btn" onClick={pause} disabled={loading || !canPause}>
          Pause
        </button>
        <button className="btn danger" onClick={stop} disabled={loading || !canStop}>
          Stop
        </button>

        <button
          className="btn"
          style={{ marginLeft: "auto" }}
          onClick={refreshStatus}
          disabled={!campaignId || loading}
          title="Refresh campaign status"
        >
          Refresh
        </button>
      </div>

      {msg ? <p style={{ marginTop: 10 }}>{msg}</p> : null}

      <div style={{ marginTop: 12 }}>
        <button className="btn" onClick={() => setShowAdvanced(!showAdvanced)}>
          {showAdvanced ? "Hide Advanced" : "Advanced"}
        </button>

        {showAdvanced ? (
          <div className="card" style={{ marginTop: 10 }}>
            <div className="row">
              <div className="col">
                <label>Daily Send Limit</label>
                <input
                  type="number"
                  value={config.dailyLimit}
                  onChange={(e) => setConfig({ ...config, dailyLimit: Number(e.target.value) })}
                  disabled={loading}
                />
              </div>
              <div className="col">
                <label>Parallel Workers</label>
                <input
                  type="number"
                  value={config.concurrency}
                  onChange={(e) => setConfig({ ...config, concurrency: Number(e.target.value) })}
                  disabled={loading}
                />
              </div>
            </div>

            <div className="row">
              <div className="col">
                <label>Quiet Hours Start</label>
                <input
                  type="time"
                  value={config.quietHoursStart}
                  onChange={(e) => setConfig({ ...config, quietHoursStart: e.target.value })}
                  disabled={loading}
                />
              </div>
              <div className="col">
                <label>Quiet Hours End</label>
                <input
                  type="time"
                  value={config.quietHoursEnd}
                  onChange={(e) => setConfig({ ...config, quietHoursEnd: e.target.value })}
                  disabled={loading}
                />
              </div>
            </div>

            <div className="row">
              <div className="col">
                <label>Stop on negative response</label>
                <select
                  value={String(config.stopOnNegative)}
                  onChange={(e) => setConfig({ ...config, stopOnNegative: e.target.value === "true" })}
                  disabled={loading}
                >
                  <option value="true">Yes</option>
                  <option value="false">No (manual review)</option>
                </select>
              </div>
              <div className="col">
                <label>Auto-book meeting on positive intent</label>
                <select
                  value={String(config.autoBookMeeting)}
                  onChange={(e) => setConfig({ ...config, autoBookMeeting: e.target.value === "true" })}
                  disabled={loading}
                >
                  <option value="true">Yes</option>
                  <option value="false">No (request approval)</option>
                </select>
              </div>
            </div>

            <div style={{ color: "#777", marginTop: 8, fontSize: 13 }}>
              Advanced settings are v1 placeholders unless you wire a run-config endpoint.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
