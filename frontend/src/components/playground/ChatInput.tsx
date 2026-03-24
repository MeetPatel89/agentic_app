import { memo, useCallback } from "react";

interface Props {
  value: string;
  isRunning: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onAbort: () => void;
}

export const ChatInput = memo(function ChatInput({
  value,
  isRunning,
  onChange,
  onSend,
  onAbort,
}: Props) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    },
    [onSend],
  );

  return (
    <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
        style={{
          flex: 1,
          resize: "none",
          borderRadius: 8,
          padding: "10px 14px",
          border: "1px solid var(--border)",
          background: "var(--bg-card)",
          color: "var(--text)",
          fontFamily: "inherit",
          fontSize: 14,
        }}
        disabled={isRunning}
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 4, justifyContent: "center" }}>
        <button
          className="btn btn-primary"
          disabled={isRunning || !value.trim()}
          onClick={onSend}
          title="Send (streaming)"
        >
          {isRunning ? "…" : "Send"}
        </button>
        {isRunning && (
          <button className="btn btn-ghost btn-sm" onClick={onAbort}>
            Stop
          </button>
        )}
      </div>
    </div>
  );
});
