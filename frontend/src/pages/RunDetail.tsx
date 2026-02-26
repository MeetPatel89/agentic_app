import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { StreamOutput } from "../components/StreamOutput";
import type { RunDetail as RunDetailType } from "../api/types";

function safeParse(json: string | null): string {
  if (!json) return "null";
  try {
    return JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    return json;
  }
}

function getOutputText(normalizedResponseJson: string | null): string {
  if (!normalizedResponseJson) return "";
  try {
    const parsed = JSON.parse(normalizedResponseJson) as { output_text?: unknown };
    return typeof parsed.output_text === "string" ? parsed.output_text : "";
  } catch {
    return "";
  }
}

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!id) return;
    setLoading(true);
    api
      .getRun(id)
      .then(setRun)
      .catch((err) => setError(err instanceof Error ? err.message : "Not found"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleExport = () => {
    if (!run) return;
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-${run.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!run) return null;
  const outputText = getOutputText(run.normalized_response_json);

  return (
    <div>
      <div className="section-header">
        <div>
          <Link to="/history" style={{ fontSize: 13 }}>
            &larr; Back to History
          </Link>
          <h2 style={{ marginTop: 8 }}>Run Detail</h2>
        </div>
        <button className="btn btn-ghost" onClick={handleExport}>
          Export JSON
        </button>
      </div>

      <div className="meta-grid">
        <div className="meta-item">
          <dt>ID</dt>
          <dd style={{ fontSize: 11 }}>{run.id}</dd>
        </div>
        <div className="meta-item">
          <dt>Created</dt>
          <dd>{new Date(run.created_at).toLocaleString()}</dd>
        </div>
        <div className="meta-item">
          <dt>Provider</dt>
          <dd>{run.provider}</dd>
        </div>
        <div className="meta-item">
          <dt>Model</dt>
          <dd>{run.model}</dd>
        </div>
        <div className="meta-item">
          <dt>Status</dt>
          <dd>
            <span
              className={`badge ${run.status === "success" ? "badge-success" : run.status === "error" ? "badge-error" : "badge-pending"}`}
            >
              {run.status}
            </span>
          </dd>
        </div>
        <div className="meta-item">
          <dt>Latency</dt>
          <dd>{run.latency_ms != null ? `${Math.round(run.latency_ms)}ms` : "—"}</dd>
        </div>
        <div className="meta-item">
          <dt>Prompt Tokens</dt>
          <dd>{run.prompt_tokens ?? "—"}</dd>
        </div>
        <div className="meta-item">
          <dt>Completion Tokens</dt>
          <dd>{run.completion_tokens ?? "—"}</dd>
        </div>
        <div className="meta-item">
          <dt>Total Tokens</dt>
          <dd>{run.total_tokens ?? "—"}</dd>
        </div>
        {run.trace_id && (
          <div className="meta-item">
            <dt>Trace ID</dt>
            <dd style={{ fontSize: 11 }}>{run.trace_id}</dd>
          </div>
        )}
      </div>

      {run.error_message && <div className="error-box mt-16">{run.error_message}</div>}

      <div className="mt-24">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Request</h3>
        <pre className="json-block">{safeParse(run.request_json)}</pre>
      </div>

      <div className="mt-24">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Rendered Output</h3>
        <StreamOutput text={outputText} isStreaming={false} />
      </div>

      <div className="mt-24">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Normalized Response</h3>
        <pre className="json-block">{safeParse(run.normalized_response_json)}</pre>
      </div>

      <div className="mt-24">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Raw Response</h3>
        <pre className="json-block">{safeParse(run.raw_response_json)}</pre>
      </div>
    </div>
  );
}
