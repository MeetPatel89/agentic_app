import { memo } from "react";
import type { ToolDefinition, ToolMode } from "../../api/types";
import { ToolModeDetails } from "./ToolModeDetails";

interface Props {
  availableTools: ToolDefinition[];
  enabledToolNames: string[];
  toolMode: ToolMode;
  onToolModeChange: (value: ToolMode) => void;
  onToolToggle: (name: string) => void;
}

export const ToolSettingsSection = memo(function ToolSettingsSection({
  availableTools,
  enabledToolNames,
  toolMode,
  onToolModeChange,
  onToolToggle,
}: Props) {
  if (availableTools.length === 0) return null;

  return (
    <div className="form-group full-width">
      <label>Tool Mode</label>
      <div style={{ display: "flex", gap: 0, marginBottom: 8 }}>
        {(["off", "auto", "manual"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => onToolModeChange(mode)}
            style={{
              flex: 1,
              padding: "6px 12px",
              border: "1px solid var(--border)",
              borderRight: mode !== "manual" ? "none" : undefined,
              borderRadius:
                mode === "off" ? "4px 0 0 4px" : mode === "manual" ? "0 4px 4px 0" : "0",
              background: toolMode === mode ? "var(--accent)" : "var(--bg-input)",
              color: toolMode === mode ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontWeight: toolMode === mode ? 600 : 400,
              fontSize: 13,
              textTransform: "capitalize",
            }}
          >
            {mode}
          </button>
        ))}
      </div>
      <ToolModeDetails
        availableTools={availableTools}
        enabledToolNames={enabledToolNames}
        toolMode={toolMode}
        onToolToggle={onToolToggle}
      />
    </div>
  );
});
