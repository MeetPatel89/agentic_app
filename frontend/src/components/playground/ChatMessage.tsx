import { memo } from "react";
import { StreamOutput } from "../StreamOutput";

interface Props {
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
}

export const ChatMessage = memo(function ChatMessage({ role, content, isStreaming }: Props) {

  return (
    <div
      style={{
        marginBottom: 16,
        display: "flex",
        flexDirection: "column",
        alignItems: role === "user" ? "flex-end" : "flex-start",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          textTransform: "uppercase",
          color: "var(--text-muted)",
          marginBottom: 4,
          letterSpacing: "0.05em",
        }}
      >
        {role}
      </div>
      <div
        style={{
          maxWidth: "85%",
          padding: "10px 14px",
          borderRadius: 12,
          background:
            role === "user"
              ? "var(--accent)"
              : "var(--bg-input)",
          color:
            role === "user"
              ? "#fff"
              : "var(--text)",
        }}
      >
        {role === "assistant" ? (
          <StreamOutput text={content} isStreaming={isStreaming} />
        ) : (
          <div style={{ whiteSpace: "pre-wrap" }}>{content}</div>
        )}
      </div>
    </div>
  );
});
