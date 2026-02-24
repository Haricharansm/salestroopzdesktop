import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

/**
 * Production Metrics Panel
 * Fetches: GET /campaign/{id}/metrics
 */
export default function MetricsPanel({ campaignId }) {
  const [m, setM] = useState({
    leadsTotal: 0,
    inSequence: 0,
    replied: 0,
    positive: 0,
    negative: 0,
    meetings: 0,
  });

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    if (!campaignId) return;

    setErr("");
    setLoading(true);

    try {
      const data = await api.getCampaignMetrics(campaignId);
      setM({
        leadsTotal: data?.leadsTotal ?? 0,
        inSequence: data?.inSequence ?? 0,
        replied: data?.replied ?? 0,
        positive: data?.positive ?? 0,
        negative: data?.negative ?? 0,
        meetings: data?.meetings ?? 0,
      });
    } catch (e) {
      setErr(e?.message || String(e));
      setM({
        leadsTotal: 0,
        inSequence: 0,
        replied: 0,
        positive: 0,
        negative: 0,
        meetings: 0,
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const cards = useMemo(
    () => [
      { k: "Leads", v: m.leadsTotal },
      { k: "In Sequence", v: m.inSequence },
      { k: "Replies", v: m.replied },
      { k: "Positive", v: m.positive },
      { k: "Negative", v: m.negative },
      { k: "Meetings", v: m.meetings },
    ],
    [m]
  );

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginBottom: 0 }}>Outcomes</h2>
        <button
          className="btn"
          onClick={load}
          disabled={!campaignId || loading}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {err ? (
        <div className="card" style={{ marginTop: 10 }}>
          <span className="badge warn">{err}</span>
        </div>
      ) : null}

      {!campaignId ? (
        <p style={{ marginTop: 8, opacity: 0.85 }}>
          Launch a campaign to see performance metrics.
        </p>
      ) : null}

      {campaignId ? (
        <div className="row" style={{ marginTop: 10 }}>
          {cards.map((c) => (
            <div
              key={c.k}
              className="card"
              style={{ padding: 10, minWidth: 140 }}
            >
              <div className="mono" style={{ color: "var(--muted)" }}>
                {c.k}
              </div>
              <div style={{ fontSize: 20, fontWeight: 800 }}>
                {c.v}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
