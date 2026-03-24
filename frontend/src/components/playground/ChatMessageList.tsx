import { memo, useCallback, useEffect, useRef } from "react";
import { ChatMessage } from "./ChatMessage";

interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  messages: ChatMessageData[];
  streamingText: string;
  isStreaming: boolean;
  isRunning: boolean;
}

/** Pixel threshold — if the user is within this distance of the bottom, auto-scroll. */
const SCROLL_THRESHOLD = 60;

export const ChatMessageList = memo(function ChatMessageList({
  messages,
  streamingText,
  isStreaming,
  isRunning,
}: Props) {

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  /**
   * true  = user is at/near the bottom → we should auto-scroll
   * false = user has scrolled up → leave them alone
   *
   * We distinguish programmatic scrolls from user scrolls by setting a flag
   * before we call scrollTop = ..., and clearing it in a microtask.
   */
  const stickToBottomRef = useRef(true);
  const isProgrammaticScrollRef = useRef(false);
  const prevMessagesLenRef = useRef(messages.length);

  /** Called on every scroll event on the container. */
  const handleScroll = useCallback(() => {
    // Ignore scroll events that we triggered ourselves.
    if (isProgrammaticScrollRef.current) return;

    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distanceFromBottom <= SCROLL_THRESHOLD;
  }, []);

  /** Scroll to bottom instantly (no animation to avoid fighting the user). */
  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    isProgrammaticScrollRef.current = true;
    el.scrollTop = el.scrollHeight;
    // Clear the flag after the browser has processed the scroll event.
    requestAnimationFrame(() => {
      isProgrammaticScrollRef.current = false;
    });
  }, []);

  // When a new message is added (user sends), always re-stick and scroll.
  useEffect(() => {
    if (messages.length > prevMessagesLenRef.current) {
      stickToBottomRef.current = true;
      scrollToBottom();
    }
    prevMessagesLenRef.current = messages.length;
  }, [messages.length, scrollToBottom]);

  // During streaming, auto-scroll only if we're still stuck to bottom.
  useEffect(() => {
    if (stickToBottomRef.current) {
      scrollToBottom();
    }
  }, [streamingText, scrollToBottom]);

  return (
    <div
      className="card"
      style={{
        flex: 1,
        overflow: "auto",
        display: "flex",
        flexDirection: "column",
        padding: 0,
        minHeight: 300,
      }}
    >
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}
      >
        {messages.length === 0 && !isRunning && (
          <div style={{ color: "var(--text-muted)", textAlign: "center", padding: "40px 0" }}>
            Send a message to start a conversation.
          </div>
        )}

        {messages.map((msg, i) => {
          const isLastAssistant = msg.role === "assistant" && i === messages.length - 1;
          const isStreamingThis = isLastAssistant && isStreaming;
          const displayContent = isStreamingThis ? streamingText : msg.content;

          return (
            <ChatMessage
              key={i}
              role={msg.role}
              content={displayContent}
              isStreaming={isStreamingThis}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
});
