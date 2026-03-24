import { memo } from "react";

interface Props {
  conversationId: string | null;
  showSettings: boolean;
  onToggleSettings: () => void;
  onNewConversation: () => void;
}

export const PlaygroundHeader = memo(function PlaygroundHeader({
  conversationId,
  showSettings,
  onToggleSettings,
  onNewConversation,
}: Props) {
  return (
    <div className="section-header">
      <h2>AI Playground</h2>
      <div className="flex gap-8" style={{ alignItems: "center" }}>
        {conversationId && (
          <span style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {conversationId.slice(0, 8)}…
          </span>
        )}
        <button className="btn btn-ghost btn-sm" onClick={onToggleSettings}>
          Settings {showSettings ? "▲" : "▼"}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onNewConversation}>
          New Chat
        </button>
      </div>
    </div>
  );
});
