import { useEffect, useMemo, useState } from "react";
import WorkspaceForm from "./WorkspaceForm";
import CSVUpload from "./CSVUpload";
import LeadsPanel from "./LeadsPanel";
import { api } from "../api";

/**
 * Setup Wizard steps:
 * 1) Workspace
 * 2) Connect M365
 * 3) Upload Leads
 * 4) Launch
 *
 * Minimal & intuitive: user only sees what's needed.
 */
export default function SetupWizard({ onLaunched }) {
  const [step, setStep] = useState(1);

  // Workspace fields
  const [workspace, setWorkspace] = useState({
    company_name: "",
    offering: "",
    icp: "",
  });

  const [workspaceSaved, setWorkspaceSaved] = useState(false);
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [error, setError] = useState("");

  // M365 state
  const [m365Status, setM365Status] = useState(null);
  const [deviceInfo, setDeviceInfo] = useState(null);
  const [m365Busy, setM365Busy] = useState(false);

  // Leads
  // If your backend requires a campaignId to upload, we’ll generate/create at step 4.
  // For now we allow upload in step 3; if campaignId is required, CSVUpload should handle “no campaign yet”.
  const [tempCampaignId, setTempCampaignId] = useState(null);

  // Launch
  const [launching, setLaunching] = useState(false);

  // ---- Helpers ----
  const steps = useMemo(
    () => [
      { id: 1, title: "Workspace", desc: "Company + Offering + ICP" },
      { id: 2, title: "Microsoft 365", desc: "Connect your mailbox (device flow)" },
      { id: 3, title: "Leads", desc: "Upload your contacts CSV" },
      { id: 4, title: "Launch", desc: "Start campaign and send first email" },
    ],
    []
  );

  const canContinueFromStep1 =
    workspace.company_name.trim() && workspace.offering.trim() && workspace.icp.trim();

  useEffect(() => {
    if (step === 2) refreshM365Status();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  async function refreshM365Status() {
    try {
      const s = await api.m365Status();
      setM365Status(s);
    } catch (e) {
      // If endpoint not ready, treat as not connected for UI
      setM365Status({ connected: false, error: e?.message || String(e) });
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
      if (typeof api.saveWorkspace === "function") {
        await api.saveWorkspace(workspace);
      } else {
        await api.createWorkspace(workspace);
      }
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
      // Expecting something like:
      // { user_code, verification_uri, message, expires_in }
      setDeviceInfo(info);
      // open browser if verification url exists
      if (info?.verification_uri) window.open(info.verification_uri, "_blank");
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setM365Busy(false);
    }
  }

  async function completeDeviceFlow() {
    setError("");
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
      // Ensure workspace saved
      if (!workspaceSaved) {
        const ok = await saveWorkspaceOnly();
        if (!ok) return;
      }

      // Launch agent
      const res = await api.launchAgent({
        offering: workspace.offering,
        icp: workspace.icp,
      });

      const newCampaignId = res?.campaign_id ?? res?.id ?? res?.campaignId ?? null;
      if (!newCampaignId) {
        throw new Error(`Launch succeeded but no campaign id returned: ${JSON.stringify(res)}`);
      }

      setTempCampaignId(newCampaignId);

      // v1: Switch to dashboard immediately
      onLaunched(newCampaignId);
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setLaunching(false);
    }
  }

  function goNext() {
    setError("");
    setStep((s) => Math.min(4, s + 1));
  }

  function goBack() {
    setError("");
    setStep((s) => Math.max(1, s - 1));
  }

  return (
    <div style={{ marginTop: 14 }}>
      {/* Stepper */}
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Setup</h2>
          <span className="badge">Step {step} of 4</span>
        </div>

        <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
          {steps.map((s) => (
            <div
              key={s.id}
              style={{
                padding: 10,
                borderRadius: 10,
                border: "1px solid #eee",
                background: s.id === step ? "#fafafa" : "white",
              }}
            >
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>
                  {s.id}. {s.title}
                </strong>
                {s.id < step ? <span className="badge good">Done</span> : null}
              </div>
              <div style={{ color: "#666", marginTop: 4 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {error ? (
        <div className="card" style={{ marginBottom: 12 }}>
          <span className="badge warn">{error}</span>
        </div>
      ) : null}

      {/* Step Content */}
      {step === 1 ? (
        <div className="card">
          <h2>Workspace</h2>
          <p style={{ marginTop: 6, color: "#666" }}>
            Tell the agent what you sell and who you sell to.
          </p>

          <WorkspaceForm
            value={workspace}
            onChange={setWorkspace}
            onSave={async () => {
              const ok = await saveWorkspaceOnly();
              if (ok) goNext();
            }}
            saving={workspaceSaving}
          />

          <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
            <button
              className="btn primary"
              onClick={async () => {
                const ok = await saveWorkspaceOnly();
                if (ok) goNext();
              }}
              disabled={workspaceSaving}
            >
              Save & Continue
            </button>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="card">
          <h2>Connect Microsoft 365</h2>
          <p style={{ marginTop: 6, color: "#666" }}>
            Connect your Outlook mailbox so Salestroopz can send the first email.
          </p>

          <div className="row" style={{ marginTop: 10, gap: 10, alignItems: "center" }}>
            {m365Status?.connected ? (
              <span className="badge good">Connected</span>
            ) : (
              <span className="badge warn">Not Connected</span>
            )}

            {m365Status?.user ? (
              <span style={{ color: "#444" }}>Signed in as: {m365Status.user}</span>
            ) : null}
          </div>

          {deviceInfo ? (
            <div className="card" style={{ marginTop: 12 }}>
              <h3 style={{ marginTop: 0 }}>Device Login</h3>
              <p style={{ color: "#666" }}>
                Enter this code in the browser window that opened:
              </p>
              <div className="row" style={{ gap: 10, alignItems: "center" }}>
                <code style={{ fontSize: 18, fontWeight: 700 }}>{deviceInfo.user_code}</code>
                <button
                  className="btn"
                  onClick={() => navigator.clipboard.writeText(deviceInfo.user_code)}
                >
                  Copy Code
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                <button className="btn primary" onClick={completeDeviceFlow} disabled={m365Busy}>
                  I’ve completed login
                </button>
              </div>
            </div>
          ) : (
            <div className="row" style={{ marginTop: 12, gap: 10 }}>
              <button className="btn primary" onClick={startDeviceFlow} disabled={m365Busy}>
                Connect
              </button>
              <button className="btn" onClick={refreshM365Status} disabled={m365Busy}>
                Refresh Status
              </button>
            </div>
          )}

          <div className="row" style={{ marginTop: 14, justifyContent: "space-between" }}>
            <button className="btn" onClick={goBack}>
              Back
            </button>
            <button className="btn primary" onClick={goNext}>
              Continue
            </button>
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="card">
          <h2>Upload Leads</h2>
          <p style={{ marginTop: 6, color: "#666" }}>
            Upload a CSV of contacts (name, email, company, title…). You can add more later.
          </p>

          <div style={{ marginTop: 10 }}>
            <CSVUpload campaignId={tempCampaignId} />
          </div>

          <div style={{ marginTop: 12 }}>
            <LeadsPanel campaignId={tempCampaignId} />
          </div>

          <div className="row" style={{ marginTop: 14, justifyContent: "space-between" }}>
            <button className="btn" onClick={goBack}>
              Back
            </button>
            <button className="btn primary" onClick={goNext}>
              Continue
            </button>
          </div>
        </div>
      ) : null}

      {step === 4 ? (
        <div className="card">
          <h2>Launch Campaign</h2>
          <p style={{ marginTop: 6, color: "#666" }}>
            We’ll generate a campaign plan and send the first email.
          </p>

          <div className="row" style={{ marginTop: 12, gap: 10 }}>
            <button className="btn" onClick={goBack} disabled={launching}>
              Back
            </button>
            <button className="btn primary" onClick={launch} disabled={launching}>
              {launching ? "Launching…" : "Launch Campaign"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
