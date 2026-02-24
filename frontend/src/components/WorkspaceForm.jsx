// frontend/src/components/WorkspaceForm.jsx
import { useState } from "react";

/**
 * Reusable workspace form.
 * Parent controls button label + save behavior (save-only or save+continue etc.)
 */
export default function WorkspaceForm({
  value,
  onChange,
  onSave,
  saving,
  primaryLabel = "Save",
}) {
  const v = value || {};
  const [localError, setLocalError] = useState("");

  const set = (k, val) => onChange({ ...v, [k]: val });

  const handleSave = async () => {
    setLocalError("");
    try {
      await onSave?.();
    } catch (e) {
      setLocalError(e?.message || String(e));
    }
  };

  return (
    <div>
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
        <button className="btn primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : primaryLabel}
        </button>
      </div>

      {localError ? (
        <div className="toast error" style={{ marginTop: 10 }}>
          {localError}
        </div>
      ) : null}
    </div>
  );
}
