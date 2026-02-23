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

  // Workspace state (what user fills)
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

  // helper: shape expected by backend (Pydantic dict_type)
  const launchPayloadFromWorkspace = (ws) => ({
    company_name: ws.company_name,
    offering: { text: ws.offering },
    icp: { text: ws.icp },
  });

  async function saveAndLaunch() {
    setLaunchError("");

    // small validation
    if (!workspace.company_name?.trim() || !workspace.offering?.trim() || !workspace.icp?.trim()) {
      setLaunchError("Please fill Company Name, Offering, and ICP.");
      return;
    }

    setLaunching(true);
    try {
      // 1) Save workspace to SQLite (support both api.saveWorkspace and api.createWorkspace)
      if (typeof api.saveWorkspace === "function") {
        await api.saveWorkspace(workspace);
      } else if (typeof api.createWorkspace === "function") {
        await api.createWorkspace(workspace);
      } else {
        throw new Error("API misconfigured: missing saveWorkspace/createWorkspace in frontend api.js");
      }

      // 2) Launch agent (backend expects offering/icp as dicts)
      if (typeof api.launchAgent !== "function") {
        throw new Error("API misconfigured: missing launchAgent in frontend api.js");
      }

      const res = await api.launchAgent(launchPayloadFromWorkspace(workspace));

      // Be defensive about response shape
      const newCampaignId = res?.campaign_id ?? res?.id ?? res?.campaignId ?? null;
      if (!newCampaignId) {
        // If backend returns a different object, show it
        throw new Error(`Launch succeeded but no campaign id returned: ${JSON.stringify(res)}`);
      }

      setCampaignId(newCampaignId);
    } catch (e) {
      setLaunchError(e?.message || String(e));
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div style={{ marginTop: 14 }}>
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
          <div
            className="row"
            style={{ justifyContent: "space-between", alignItems: "center" }}
          >
            <h2>Autonomous Orchestration</h2>
            {healthBadge}
          </div>

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
