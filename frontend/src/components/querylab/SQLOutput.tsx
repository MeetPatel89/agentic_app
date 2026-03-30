import { memo, useCallback } from "react";

interface Props {
  sql: string;
  explanation: string;
  dialect: string;
  isStreaming?: boolean;
}

export const SQLOutput = memo(function SQLOutput({ sql, explanation, dialect, isStreaming }: Props) {
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(sql);
  }, [sql]);

  if (!sql && !isStreaming) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <label style={{ margin: 0 }}>
          Generated SQL
          <span
            className="badge"
            style={{
              marginLeft: 8,
              background: "var(--bg-input)",
              color: "var(--text-muted)",
              fontSize: 10,
              textTransform: "uppercase",
            }}
          >
            {dialect}
          </span>
        </label>
        {sql && !isStreaming && (
          <button className="btn btn-ghost btn-sm" onClick={handleCopy} type="button">
            Copy
          </button>
        )}
      </div>
      <pre
        className={isStreaming ? "output-panel streaming" : "output-panel"}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          margin: 0,
          minHeight: isStreaming ? 48 : undefined,
        }}
      >
        {isStreaming ? (
          <code style={{ color: "var(--text-muted)" }}>Generating SQL…</code>
        ) : (
          <code>{sql}</code>
        )}
        {isStreaming && <span className="cursor-blink" />}
      </pre>
      {explanation && !isStreaming && (
        <div
          style={{
            marginTop: 8,
            padding: "8px 12px",
            background: "var(--bg-input)",
            borderRadius: "var(--radius)",
            fontSize: 13,
            color: "var(--text-muted)",
          }}
        >
          {explanation}
        </div>
      )}
    </div>
  );
});
