import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_AGENT_URL || "http://127.0.0.1:8715";

export default function RunControls({ campaignId }) {
  const [state, setState] = useState("idle"); // idle | running | paused
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const [config, setConfig] = useState({
    dailyLimit: 80,
    concurrency: 4,
    quietHoursStart: "20:00",
    quietHoursEnd: "07:00",
    stopOnNegative: true,
    autoBookMeeting: true,
  });

  const badgeText = useMemo(() => (campaignId ? state.toUpperCase() : "NO CAMPAIGN"), [state, campaignId]);

  // Optional: if you later add GET /campaign/{id} to fetch status, you can refresh here.
  useEffect(() => {
    setMsg("");
    if (!campaignId) setState("idle");
  }, [campaignId]);

  const start = async () => {
    if (!campaignId) {
      setMsg("⚠️ Create/select a campaign first (save sequence).");
      return;
    }

    try {
      setLoading(true);
      setMsg("");

      // 1) Start campaign run
      const res = await fetch(`${API_BASE}/campaign/${campaignId}/start`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Failed to start campaign");

      // 2) (Optional, Phase-2) Save run config to backend if you add an endpoint:
      // await fetch(`${API_BASE}/campaign/${campaignId}/run-config`, { ... })

      setState("running");
      setMsg("✅ Run started. Agent will begin processing due leads.");
    } catch (e) {
      setMsg(`❌ ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const pause = async () => {
    if (!campaignId) return;

    try {
      setLoading(true);
      setMsg("");

      const res = await fetch(`${API_BASE}/campaign/${campaignId}/pause`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Failed to pause campaign");

      setState("paused");
      setMsg("⏸️ Paused.");
    } catch (e) {
      setMsg(`❌ ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const stop = async () => {
    // For MVP we map Stop -> paused (or add /stop endpoint later)
    if (!campaignId) return;

    try {
      setLoading(true);
      setMsg("");

      // If you add /campaign/{id}/stop endpoint later, call it here.
      // For now, set to paused (safe stop)
      const res = await fetch(`${API_BASE}/campaign/${campaignId}/pause`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Failed to stop campaign");

      setState("idle");
      setMsg("🛑 Stopped (set to paused/idle).");
    } catch (e) {
      setMsg(`❌ ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2>Run Controls</h2>
        <span className="badge">{badgeText}</span>
      </div>

      {!campaignId ? (
        <p style={{ marginTop: 8, opacity: 0.85 }}>
          Create a campaign first (Save Sequence). Then you can Start/Pause the run.
        </p>
      ) : null}

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

      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn primary" onClick={start} disabled={loading || !campaignId || state === "running"}>
          {loading && state !== "paused" ? "Starting..." : "Start"}
        </button>
        <button className="btn" onClick={pause} disabled={loading || !campaignId || state !== "running"}>
          Pause
        </button>
        <button className="btn danger" onClick={stop} disabled={loading || !campaignId || state === "idle"}>
          Stop
        </button>
      </div>

      {msg ? <p style={{ marginTop: 10 }}>{msg}</p> : null}

      <p style={{ marginTop: 10 }}>
        This will orchestrate the loop: generate → send → wait → detect reply → branch → repeat until meeting or “no”.
      </p>
    </div>
  );
}
