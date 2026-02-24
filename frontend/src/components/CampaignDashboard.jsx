import { useEffect, useMemo, useState } from "react";
import RunControls from "./RunControls";
import MetricsPanel from "./MetricsPanel";
import ActivityPanel from "./ActivityPanel";
import LeadsPanel from "./LeadsPanel";
import { api } from "../api";

/**
 * Dashboard-only view after launch.
 * Keep it clean: KPIs + activity + actions.
 */
export default function CampaignDashboard({ campaignId, onReset }) {
  const [ollamaOk, setOllamaOk] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.ollamaStatus();
        setOllamaOk(!!res?.ollama_running);
      } catch {
        setOllamaOk(false);
      }
    })();
  }, []);

  const healthBadge = useMemo(() => {
    if (ollamaOk === null) return <span className="badge">Checking LLM…</span>;
    if (ollamaOk) return <span className="badge good">Ollama Running</span>;
    return <span className="badge warn">Ollama Not Reachable</span>;
  }, [ollamaOk]);

  return (
    <div style={{ marginTop: 14 }}>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ marginBottom: 4 }}>Campaign Dashboard</h2>
            <div style={{ color: "#666" }}>Campaign ID: {campaignId}</div>
          </div>
          <div className="row" style={{ gap: 10, alignItems: "center" }}>
            {healthBadge}
            <button className="btn" onClick={onReset} title="Start over with a new setup">
              New Setup
            </button>
          </div>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <RunControls campaignId={campaignId} />
          <div style={{ height: 12 }} />
          <MetricsPanel campaignId={campaignId} />
          <div style={{ height: 12 }} />
          <ActivityPanel campaignId={campaignId} />
        </div>

        <div className="card">
          <h2>Leads</h2>
          <p style={{ marginTop: 6, color: "#666" }}>
            Upload more leads any time from Advanced (v1 keeps this simple).
          </p>
          <LeadsPanel campaignId={campaignId} />
        </div>
      </div>
    </div>
  );
}
