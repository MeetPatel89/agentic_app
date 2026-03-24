import { memo } from "react";
import type { SQLValidationResult } from "../../api/types";

interface Props {
  validation: SQLValidationResult | null;
}

export const ValidationPanel = memo(function ValidationPanel({ validation }: Props) {
  if (!validation) return null;

  const statusColor = validation.is_valid ? "var(--success)" : "var(--error)";
  const statusBg = validation.is_valid ? "var(--badge-success-bg)" : "var(--badge-error-bg)";

  return (
    <div
      style={{
        marginTop: 12,
        padding: "12px 16px",
        borderRadius: "var(--radius)",
        border: `1px solid ${statusColor}`,
        background: statusBg,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: validation.syntax_errors.length > 0 ? 8 : 0 }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: statusColor }}>
          {validation.is_valid ? "Valid SQL" : "Invalid SQL"}
        </span>
        {validation.sandbox_execution_success !== null && (
          <span
            className="badge"
            style={{
              background: validation.sandbox_execution_success ? "var(--badge-success-bg)" : "var(--badge-error-bg)",
              color: validation.sandbox_execution_success ? "var(--success)" : "var(--error)",
            }}
          >
            Sandbox: {validation.sandbox_execution_success ? "passed" : "failed"}
          </span>
        )}
      </div>
      {validation.syntax_errors.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: "var(--error)" }}>
          {validation.syntax_errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
      )}
      {validation.sandbox_error && (
        <div style={{ marginTop: 4, fontSize: 12, color: "var(--error)" }}>
          {validation.sandbox_error}
        </div>
      )}
    </div>
  );
});
