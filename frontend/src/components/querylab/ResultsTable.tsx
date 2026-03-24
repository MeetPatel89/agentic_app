import { memo } from "react";
import type { SQLExecuteResponse } from "../../api/types";

interface Props {
  result: SQLExecuteResponse | null;
}

export const ResultsTable = memo(function ResultsTable({ result }: Props) {
  if (!result) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <label style={{ margin: 0 }}>
          Results
          <span style={{ fontWeight: 400, fontSize: 12, color: "var(--text-muted)", marginLeft: 8 }}>
            {result.row_count} row{result.row_count !== 1 ? "s" : ""} in {result.execution_time_ms.toFixed(1)}ms
            {result.truncated && " (truncated)"}
          </span>
        </label>
      </div>
      <div style={{ overflowX: "auto", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
        <table className="data-table">
          <thead>
            <tr>
              {result.columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>{cell === null ? <span style={{ color: "var(--text-muted)" }}>NULL</span> : String(cell)}</td>
                ))}
              </tr>
            ))}
            {result.rows.length === 0 && (
              <tr>
                <td colSpan={result.columns.length} style={{ textAlign: "center", color: "var(--text-muted)" }}>
                  No rows returned
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
});
