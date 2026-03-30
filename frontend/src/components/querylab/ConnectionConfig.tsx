import { memo } from "react";

interface Props {
  connectionString: string;
  onChange: (value: string) => void;
}

export const ConnectionConfig = memo(function ConnectionConfig({ connectionString, onChange }: Props) {
  return (
    <div className="form-group full-width">
      <label>Connection String (for execution)</label>
      <input
        type="password"
        value={connectionString}
        onChange={(e) => onChange(e.target.value)}
        placeholder="postgresql+asyncpg://user:pass@host:5432/dbname"
        autoComplete="off"
      />
      <span style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
        Supported: postgresql+asyncpg, mysql+aiomysql, sqlite+aiosqlite, mssql+aioodbc
      </span>
    </div>
  );
});
