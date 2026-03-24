import { memo } from "react";
import type { SQLDialect } from "../../api/types";

const DIALECTS: { value: SQLDialect; label: string }[] = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "tsql", label: "T-SQL (SQL Server)" },
  { value: "mysql", label: "MySQL" },
  { value: "sqlite", label: "SQLite" },
  { value: "bigquery", label: "BigQuery" },
  { value: "snowflake", label: "Snowflake" },
];

interface Props {
  value: SQLDialect;
  onChange: (dialect: SQLDialect) => void;
}

export const DialectSelector = memo(function DialectSelector({ value, onChange }: Props) {
  return (
    <div className="form-group">
      <label>SQL Dialect</label>
      <select value={value} onChange={(e) => onChange(e.target.value as SQLDialect)}>
        {DIALECTS.map((d) => (
          <option key={d.value} value={d.value}>
            {d.label}
          </option>
        ))}
      </select>
    </div>
  );
});
