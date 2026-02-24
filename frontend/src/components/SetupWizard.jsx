import { useEffect, useMemo, useState } from "react";
import WorkspaceForm from "./WorkspaceForm";
import CSVUpload from "./CSVUpload";
import LeadsPanel from "./LeadsPanel";
import { api } from "../api";

export default function SetupWizard({ onLaunched }) {
  const [step, setStep] = useState(1);

  const [workspace, setWorkspace] = useState({
    company_name: "",
    offering: "",
    icp: "",
  });

  const [workspaceSaved, setWorkspaceSaved] = useState(false);
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [error, setError] = useState("");

  const [m365Status, setM365Status] = useState(null);
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [m365Busy, setM365Busy] = useState(false);

  const [campaignId, setCampaignId] = useState(null);
  const [launching, setLaunching] = useState(false);

  const steps = useMemo(
    () => [
      { id: 1, title: "Workspace" },
      { id: 2, title: "Microsoft 365" },
      { id: 3, title: "Launch Campaign" },
      { id: 4, title: "Upload Leads" },
    ],
    []
  );

  const canContinueFromStep1 =
    workspace.company_name.trim() &&
    workspace.offering.trim() &&
    workspace.icp.trim();

  useEffect(() => {
    if (step === 2) refreshM365Status();
  }, [step]);

  async function refreshM365Status() {
    try {
      const s = await api.m365Status();
      setM365Status(s);
    } catch {
      setM365Status({ connected: false });
    }
  }

  async function saveWorkspaceOnly() {
    setError("");
    if (!canContinueFromStep1) {
      setError("Please fill Company Name, Offering, and ICP.");
      return false;
    }

    setWorkspaceSaving(true);
    try {
      await api.saveWorkspace(workspace);
      setWorkspaceSaved(true);
      return true;
    } catch (e) {
      setError(e?.message || String(e));
      return false;
    } finally {
      setWorkspaceSaving(false);
    }
  }

  async function startDeviceFlow() {
    setError("");
    setM365Busy(true);
    try {
      const info = await api.m365DeviceStart();
      setDeviceInfo(info);
      if (info?.verification_uri) window.open(info.verification_uri, "_blank");
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setM365Busy(false);
    }
  }

  async function completeDeviceFlow() {
    setM365Busy(true);
    try {
      await api.m365DeviceComplete();
      await refreshM365Status();
      setDeviceInfo(null);
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setM365Busy(false);
    }
  }

  async function launch() {
    setError("");
    setLaunching(true);

    try {
      if (!workspaceSaved) {
        const ok = await saveWorkspaceOnly();
        if (!ok) return;
      }

      const res = await api.launchAgent({
        offering: workspace.offering,
        icp: workspace.icp,
      });

      const id = res?.campaign_id ?? res?.id ?? null;
      if (!id) throw new Error("Launch succeeded but no campaign ID returned");

      setCampaignId(id);
      setStep(4);
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setLaunching(false);
    }
  }

  function finishSetup() {
    onLaunched(campaignId);
  }

  return (
    <div style={{ marginTop: 14 }}>
      <div className="card" style={{ marginBottom: 12 }}>
        <h2>Setup</h2>
        <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
          {steps.map((s) => (
            <span
              key={s.id}
              className={`badge ${step === s.id ? "good" : ""}`}
            >
              {s.id}. {s.title}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div className="card">
          <span className="badge warn">{error}</span>
        </div>
      )}

      {/* STEP 1 */}
      {step === 1 && (
        <div className="card">
          <WorkspaceForm
            value={workspace}
            onChange={setWorkspace}
            onSave={async () => {
              const ok = await saveWorkspaceOnly();
              if (ok) setStep(2);
            }}
            saving={workspaceSaving}
            primaryLabel="Save & Continue"
          />
        </div>
      )}

      {/* STEP 2 */}
      {step === 2 && (
        <div className="card">
          <h2>Connect Microsoft 365</h2>

          {m365Status?.connected ? (
            <span className="badge good">Connected</span>
          ) : (
            <span className="badge warn">Not Connected</span>
          )}

          {deviceInfo ? (
            <div style={{ marginTop: 10 }}>
              <p>Enter this code in browser:</p>
              <strong>{deviceInfo.user_code}</strong>
              <div style={{ marginTop: 10 }}>
                <button onClick={completeDeviceFlow}>
                  I've completed login
                </button>
              </div>
            </div>
          ) : (
            <button onClick={startDeviceFlow}>
              Connect Microsoft 365
            </button>
          )}

          <div style={{ marginTop: 14 }}>
            <button onClick={() => setStep(3)}>Continue</button>
          </div>
        </div>
      )}

      {/* STEP 3 */}
      {step === 3 && (
        <div className="card">
          <h2>Launch Campaign</h2>
          <button onClick={launch} disabled={launching}>
            {launching ? "Launching..." : "Launch Campaign"}
          </button>
        </div>
      )}

      {/* STEP 4 */}
      {step === 4 && campaignId && (
        <div className="card">
          <h2>Upload Leads</h2>
          <CSVUpload campaignId={campaignId} />
          <div style={{ marginTop: 12 }}>
            <LeadsPanel campaignId={campaignId} />
          </div>

          <div style={{ marginTop: 14 }}>
            <button className="btn primary" onClick={finishSetup}>
              Go to Dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
