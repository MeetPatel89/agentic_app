import { memo } from "react";
import type { ToolDefinition, ToolMode } from "../../api/types";

interface Props {
  availableTools: ToolDefinition[];
  enabledToolNames: string[];
  toolMode: ToolMode;
  onToolToggle: (name: string) => void;
}

export const ToolModeDetails = memo(function ToolModeDetails({
  availableTools,
  enabledToolNames,
  toolMode,
  onToolToggle,
}: Props) {
  if (toolMode === "auto") {
    return (
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
        All tools available to LLM automatically (disables streaming)
      </div>
    );
  }

  if (toolMode !== "manual") return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {availableTools.map((tool) => (
        <label
          key={tool.name}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            fontWeight: "normal",
            cursor: "pointer",
            textTransform: "none",
            letterSpacing: "normal",
            fontSize: 13,
            color: "var(--text)",
          }}
        >
          <input
            type="checkbox"
            checked={enabledToolNames.includes(tool.name)}
            onChange={() => onToolToggle(tool.name)}
            style={{ width: "auto", margin: 0 }}
          />
          <span>
            <strong>{tool.name}</strong> - {tool.description}
          </span>
        </label>
      ))}
    </div>
  );
});
