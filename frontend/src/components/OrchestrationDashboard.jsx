// frontend/src/components/OrchestrationDashboard.jsx
import { useEffect, useMemo, useState } from "react";
import SequenceBuilder from "./SequenceBuilder";
import LeadsPanel from "./LeadsPanel";
import RunControls from "./RunControls";
import ActivityPanel from "./ActivityPanel";
import MetricsPanel from "./MetricsPanel";
import CSVUpload from "./CSVUpload";
import WorkspaceForm from "./WorkspaceForm";
import { api } from "../api"; // IMPORTANT: use api object

export default function OrchestrationDashboard() {
  const [ollamaOk, setOllamaOk] = useState(null);

  const [campaignId, setCampaignId] = useState(null);

  // Workspace state (THIS is what user fills)
  const [workspace, setWorkspace] = useState({
    company_name: "",
    offering: "",
    icp: "",
  });

  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState("");

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

  async function saveAndLaunch() {
    setLaunchError("");

    // tiny validation so you don't launch blanks
    if (!workspace.company_name || !workspace.offering || !workspace.icp) {
      setLaunchError("Please fill Company Name, Offering, and ICP.");
      return;
    }

    setLaunching(true);
    try {
      // 1) Save workspace to SQLite
      await api.saveWorkspace(workspace);

      // 2) Launch agent => creates campaign + status running
      const res = await api.launchAgent({
        offering: { text: workspace.offering },
        icp: { text: workspace.icp },
        workspace_id: null,
    });

      setCampaignId(res.campaign_id);
    } catch (e) {
     setLaunchError(typeof e === "string" ? e : e?.message || JSON.stringify(e));
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div style={{ marginTop: 14 }}>
      {/* TOP: Workspace input (this is what you were missing) */}
      <WorkspaceForm
        value={workspace}
        onChange={setWorkspace}
        onSave={saveAndLaunch}
        saving={launching}
      />

      {launchError ? (
        <div className="card" style={{ marginBottom: 12 }}>
          <span className="badge warn">{launchError}</span>
        </div>
      ) : null}

      <div className="grid">
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h2>Autonomous Orchestration</h2>
            {healthBadge}
          </div>

          {/* Keep sequence builder if you want, but it shouldn't be the ONLY path */}
          <SequenceBuilder
            campaignId={campaignId}
            onCampaignReady={(id) => setCampaignId(id)}
          />

          <div style={{ height: 12 }} />

          <CSVUpload campaignId={campaignId} />

          <div style={{ height: 12 }} />

          <LeadsPanel campaignId={campaignId} />
        </div>

        <div className="card">
          <RunControls campaignId={campaignId} />
          <div style={{ height: 12 }} />
          <MetricsPanel campaignId={campaignId} />
          <div style={{ height: 12 }} />
          <ActivityPanel campaignId={campaignId} />
        </div>
      </div>
    </div>
  );
}
