import { memo, useState } from "react";
import { api } from "../../api/client";
import type { SchemaContextFormat } from "../../api/types";

export type SchemaEditorMode = "auto" | "manual";

interface Props {
  mode: SchemaEditorMode;
  onModeChange: (mode: SchemaEditorMode) => void;
  /** Auto-mode schema text loaded from a live connection. */
  schemaContext: string;
  onSchemaContextChange: (value: string) => void;
  /** Manual-mode full prompt override. */
  systemPrompt: string;
  onSystemPromptChange: (value: string) => void;
  format: SchemaContextFormat;
  onFormatChange: (format: SchemaContextFormat) => void;
}

const FORMAT_OPTIONS: { value: SchemaContextFormat; label: string }[] = [
  { value: "compact_ddl", label: "Compact DDL" },
  { value: "structured_catalog", label: "Structured Catalog" },
  { value: "concise_notation", label: "Concise Notation" },
];

export const SchemaPromptEditor = memo(function SchemaPromptEditor({
  mode,
  onModeChange,
  schemaContext,
  onSchemaContextChange,
  systemPrompt,
  onSystemPromptChange,
  format,
  onFormatChange,
}: Props) {
  const [expanded, setExpanded] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tokenEstimate, setTokenEstimate] = useState<number | null>(null);
  const [tableCount, setTableCount] = useState<number | null>(null);

  const handleLoad = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const res = await api.fetchSchemaContext({ format });
      onSchemaContextChange(res.schema_text);
      setTokenEstimate(res.estimated_tokens);
      setTableCount(res.table_count);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to load schema");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="form-group full-width">
      <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span>Schema &amp; Prompt</span>
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <button
            type="button"
            className={`btn btn-sm ${mode === "auto" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => onModeChange("auto")}
          >
            Auto
          </button>
          <button
            type="button"
            className={`btn btn-sm ${mode === "manual" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => onModeChange("manual")}
            title="Use a full custom prompt override"
          >
            Manual
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </label>

      {expanded && mode === "auto" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <select
              value={format}
              onChange={(e) => onFormatChange(e.target.value as SchemaContextFormat)}
              style={{ maxWidth: 220 }}
            >
              {FORMAT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={handleLoad}
              disabled={isLoading}
            >
              {isLoading ? "Loading…" : "Load from Connection"}
            </button>
            {tableCount != null && (
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {tableCount} table{tableCount === 1 ? "" : "s"}
              </span>
            )}
            {tokenEstimate != null && (
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                ~{tokenEstimate.toLocaleString()} tokens
              </span>
            )}
          </div>
          {loadError && (
            <div className="error-box" style={{ fontSize: 12 }}>
              {loadError}
            </div>
          )}
          <textarea
            rows={12}
            value={schemaContext}
            onChange={(e) => onSchemaContextChange(e.target.value)}
            placeholder="Click 'Load from Connection' or paste a schema (DDL / catalog)."
            style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.5 }}
          />
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Auto mode injects this text into the default prompt's schema slot. Dialect guidance and
            instruction scaffolding are added for you.
          </div>
        </div>
      )}

      {expanded && mode === "manual" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <textarea
            rows={12}
            value={systemPrompt}
            onChange={(e) => onSystemPromptChange(e.target.value)}
            placeholder="Full system-prompt override. Use {dialect_guidance} to splice in dialect notes."
            style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.5 }}
          />
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Manual mode replaces the entire default template. You own prompt structure, schema
            layout, and instructions.
          </div>
        </div>
      )}
    </div>
  );
});
