// frontend/src/components/LeadsPanel.jsx
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

export default function LeadsPanel({ campaignId }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);

  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const page = useMemo(() => Math.floor(offset / limit) + 1, [offset, limit]);
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / limit)), [total, limit]);

  async function load() {
    if (!campaignId) return;
    setErr("");
    setLoading(true);
    try {
      const data = await api.getCampaignLeads(campaignId, { limit, offset });
      const list = data?.items ?? data?.leads ?? [];
      const count = data?.total ?? list.length;

      setItems(Array.isArray(list) ? list : []);
      setTotal(Number.isFinite(count) ? count : (Array.isArray(list) ? list.length : 0));
    } catch (e) {
      setErr(e?.message || String(e));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Reset paging when campaign changes
    setOffset(0);
  }, [campaignId]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId, limit, offset]);

  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div style={{ marginTop: 10 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0 }}>Leads</h3>
          <div style={{ color: "#666", marginTop: 4 }}>
            Campaign: <span className="mono">{campaignId ?? "—"}</span>
          </div>
        </div>

        <div className="row" style={{ gap: 8, alignItems: "center" }}>
          <span className="badge">Total: {total}</span>

          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={{ height: 34 }}
            title="Rows per page"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>

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

      {!campaignId ? (
        <div style={{ marginTop: 10, color: "#777" }}>
          Launch a campaign to view imported leads.
        </div>
      ) : null}

      {campaignId ? (
        <>
          <table className="table" style={{ marginTop: 10 }}>
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Company</th>
                <th>Title</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ color: "#777" }}>
                    Loading…
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ color: "#777" }}>
                    No leads yet. Upload a CSV to get started.
                  </td>
                </tr>
              ) : (
                items.map((l) => (
                  <tr key={l.id ?? `${l.email}-${l.company ?? ""}`}>
                    <td className="mono">{l.email ?? ""}</td>
                    <td>{l.name ?? l.first_name ?? ""}</td>
                    <td>{l.company ?? ""}</td>
                    <td>{l.title ?? ""}</td>
                    <td className="mono">{l.status ?? ""}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          <div className="row" style={{ marginTop: 10, justifyContent: "space-between" }}>
            <div style={{ color: "#666" }}>
              Page {page} / {totalPages}
            </div>

            <div className="row" style={{ gap: 8 }}>
              <button className="btn" disabled={!canPrev || loading} onClick={() => setOffset(Math.max(0, offset - limit))}>
                Prev
              </button>
              <button className="btn" disabled={!canNext || loading} onClick={() => setOffset(offset + limit)}>
                Next
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
