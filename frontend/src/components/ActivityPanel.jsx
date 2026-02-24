import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";

/**
 * Production Activity Panel:
 * - Fetches: GET /campaign/{id}/activity?limit=200
 * - Supports manual refresh + optional auto-refresh polling
 */
export default function ActivityPanel({ campaignId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [auto, setAuto] = useState(true);

  const timerRef = useRef(null);

  async function load() {
    if (!campaignId) return;
    setErr("");
    setLoading(true);
    try {
      const data = await api.getCampaignActivity(campaignId, { limit: 200 });
      setItems(Array.isArray(data) ? data : (data?.items || []));
    } catch (e) {
      setErr(e?.message || String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // initial load when campaign changes
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  useEffect(() => {
    // polling
    if (!campaignId) return;

    if (auto) {
      timerRef.current = setInterval(() => {
        load();
      }, 5000);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, auto]);

  const lines = useMemo(() => {
    // Backend returns [{id, lead_id, type, message, timestamp}]
    return items
      .map((e) => {
        const ts = e.timestamp ? new Date(e.timestamp).toLocaleString() : "";
        const tag = (e.type || "event").toUpperCase();
        const msg = e.message || "";
        return `${ts}  ${tag}  ${msg}`;
      })
      .join("\n");
  }, [items]);

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginBottom: 0 }}>Live Activity</h2>

        <div className="row" style={{ gap: 10, alignItems: "center" }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={auto}
              onChange={(e) => setAuto(e.target.checked)}
            />
            Auto-refresh
          </label>

          <button className="btn" onClick={load} disabled={!campaignId || loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {err ? (
        <div className="card" style={{ marginTop: 10 }}>
          <span className="badge warn">{err}</span>
        </div>
      ) : null}

      <div className="log" style={{ marginTop: 10 }}>
        <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
          {!campaignId
            ? "Launch a campaign to view activity."
            : loading && items.length === 0
            ? "Loading…"
            : items.length === 0
            ? "No activity yet."
            : lines}
        </pre>
      </div>
    </div>
  );
}
