import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { PaginatedConversations, PaginatedRuns } from "../api/types";

type ViewMode = "conversations" | "runs";

export function History() {
  const [viewMode, setViewMode] = useState<ViewMode>("conversations");

  return (
    <div>
      <div className="section-header">
        <h2>History</h2>
        <div className="flex gap-8">
          <button
            className={`btn btn-sm ${viewMode === "conversations" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setViewMode("conversations")}
          >
            Conversations
          </button>
          <button
            className={`btn btn-sm ${viewMode === "runs" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setViewMode("runs")}
          >
            Runs
          </button>
        </div>
      </div>

      {viewMode === "conversations" ? <ConversationsView /> : <RunsView />}
    </div>
  );
}

function ConversationsView() {
  const navigate = useNavigate();
  const [data, setData] = useState<PaginatedConversations | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConversations = useCallback((p: number) => {
    setLoading(true);
    setError(null);
    api
      .listConversations(p)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadConversations(page);
  }, [page, loadConversations]);

  const handleDelete = async (id: string) => {
    try {
      await api.deleteConversation(id);
      loadConversations(page);
    } catch {
      /* ignore */
    }
  };

  const handleContinue = (id: string) => {
    navigate(`/?conversation=${id}`);
  };

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <>
      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error-box">{error}</div>}

      {data && data.items.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Last Activity</th>
                <th>Title</th>
                <th>Provider</th>
                <th>Model</th>
                <th>Messages</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((conv) => (
                <tr key={conv.id}>
                  <td>{new Date(conv.updated_at).toLocaleString()}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {conv.title || <span style={{ color: "var(--text-muted)" }}>Untitled</span>}
                  </td>
                  <td>{conv.provider}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{conv.model}</td>
                  <td>{conv.message_count}</td>
                  <td>
                    <div className="flex gap-8">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleContinue(conv.id)}
                      >
                        Continue
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleDelete(conv.id)}
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
          No conversations yet. Go to the Playground to start one.
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
          <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      )}
    </>
  );
}

function RunsView() {
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
    <>
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
          <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            Next
          </button>
        </div>
      )}
    </>
  );
}
