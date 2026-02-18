import { useState } from "react";
import { createWorkspace } from "../api";

// frontend/src/components/WorkspaceForm.jsx
export default function WorkspaceForm({ value, onChange, onSave, saving }) {
  const v = value || {};

  const set = (k, val) => onChange({ ...v, [k]: val });

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <h2>Workspace (Offering + ICP)</h2>

      <label>Company Name</label>
      <input
        placeholder="e.g. Saxon.AI"
        value={v.company_name || ""}
        onChange={(e) => set("company_name", e.target.value)}
      />

      <label style={{ marginTop: 10 }}>Offering</label>
      <textarea
        placeholder="What do you sell? To whom? Why does it matter?"
        rows={5}
        value={v.offering || ""}
        onChange={(e) => set("offering", e.target.value)}
      />

      <label style={{ marginTop: 10 }}>ICP</label>
      <textarea
        placeholder="Industry, roles, size, triggers, pain points…"
        rows={5}
        value={v.icp || ""}
        onChange={(e) => set("icp", e.target.value)}
      />

      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn primary" onClick={onSave} disabled={saving}>
          {saving ? "Saving..." : "Save + Launch Agent"}
        </button>
      </div>
    </div>
  );
}
