import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { PaginatedRuns } from "../api/types";

export function History() {
  const [data, setData] = useState<PaginatedRuns | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback((p: number) => {
    setLoading(true);
    setError(null);
    api
      .listRuns(p)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRuns(page);
  }, [page, loadRuns]);

  const handleDelete = async (id: string) => {
    try {
      await api.deleteRun(id);
      loadRuns(page);
    } catch {
      /* ignore */
    }
  };

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div>
      <div className="section-header">
        <h2>Run History</h2>
        {data && <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{data.total} runs</span>}
      </div>

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error-box">{error}</div>}

      {data && data.items.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Provider</th>
                <th>Model</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Tokens</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((run) => (
                <tr key={run.id}>
                  <td>{new Date(run.created_at).toLocaleString()}</td>
                  <td>{run.provider}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{run.model}</td>
                  <td>
                    <span
                      className={`badge ${run.status === "success" ? "badge-success" : run.status === "error" ? "badge-error" : "badge-pending"}`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td>{run.latency_ms != null ? `${Math.round(run.latency_ms)}ms` : "—"}</td>
                  <td>{run.total_tokens ?? "—"}</td>
                  <td>
                    <div className="flex gap-8">
                      <Link to={`/runs/${run.id}`} className="btn btn-ghost btn-sm">
                        View
                      </Link>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleDelete(run.id)}
                        style={{ color: "var(--error)" }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.items.length === 0 && !loading && (
        <div className="card" style={{ textAlign: "center", color: "var(--text-muted)" }}>
          No runs yet. Go to the Playground to create one.
        </div>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
