import { memo, useState } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export const SchemaPromptEditor = memo(function SchemaPromptEditor({ value, onChange }: Props) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="form-group full-width">
      <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>System Prompt (Schema &amp; Context)</span>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setExpanded((e) => !e)}
          type="button"
        >
          {expanded ? "Collapse" : "Expand"}
        </button>
      </label>
      {expanded && (
        <textarea
          rows={12}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Paste your database schema, business rules, and context here..."
          style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.5 }}
        />
      )}
    </div>
  );
});
