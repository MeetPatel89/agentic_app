import { useCallback, useRef, useState } from "react";
import type {
  ChatRequest,
  ConversationTurnRequest,
  NormalizedChatResponse,
  StreamEvent,
} from "../api/types";

interface UseStreamReturn {
  streamingText: string;
  isStreaming: boolean;
  error: string | null;
  finalResponse: NormalizedChatResponse | null;
  conversationId: string | null;
  startStream: (req: ChatRequest) => void;
  startTurnStream: (req: ConversationTurnRequest) => void;
  abort: () => void;
  reset: () => void;
}

export function useStream(): UseStreamReturn {
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finalResponse, setFinalResponse] = useState<NormalizedChatResponse | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textBufferRef = useRef("");
  const rafIdRef = useRef<number | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (rafIdRef.current !== null) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    abort();
    textBufferRef.current = "";
    setStreamingText("");
    setError(null);
    setFinalResponse(null);
    setConversationId(null);
  }, [abort]);

  const runStream = useCallback(
    (url: string, body: unknown) => {
      abort();
      textBufferRef.current = "";
      setStreamingText("");
      setError(null);
      setFinalResponse(null);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      (async () => {
        try {
          const res = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: controller.signal,
          });

          if (!res.ok) {
            const errBody = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(errBody.detail || `HTTP ${res.status}`);
          }

          const reader = res.body?.getReader();
          if (!reader) throw new Error("No response body");

          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() ?? "";

            let currentEventType: string | null = null;
            for (const line of lines) {
              if (line.startsWith("event: ")) {
                currentEventType = line.slice(7).trim();
              } else if (line.startsWith("data: ") && currentEventType) {
                try {
                  const event = JSON.parse(line.slice(6)) as StreamEvent;
                  switch (currentEventType) {
                    case "delta":
                      if (event.type === "delta") {
                        textBufferRef.current += event.text;
                        if (rafIdRef.current === null) {
                          rafIdRef.current = requestAnimationFrame(() => {
                            setStreamingText(textBufferRef.current);
                            rafIdRef.current = null;
                          });
                        }
                      }
                      break;
                    case "final":
                      if (event.type === "final") {
                        setFinalResponse(event.response);
                        if (event.conversation_id) {
                          setConversationId(event.conversation_id);
                        }
                      }
                      break;
                    case "error":
                      if (event.type === "error") {
                        setError(event.message);
                      }
                      break;
                  }
                } catch {
                  // skip malformed JSON
                }
                currentEventType = null;
              }
            }
          }
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") return;
          setError(err instanceof Error ? err.message : "Stream failed");
        } finally {
          if (rafIdRef.current !== null) {
            cancelAnimationFrame(rafIdRef.current);
            rafIdRef.current = null;
          }
          setStreamingText(textBufferRef.current);
          setIsStreaming(false);
        }
      })();
    },
    [abort],
  );

  const startStream = useCallback(
    (req: ChatRequest) => runStream("/api/chat/stream", req),
    [runStream],
  );

  const startTurnStream = useCallback(
    (req: ConversationTurnRequest) => runStream("/api/chat/turn/stream", req),
    [runStream],
  );

  return {
    streamingText,
    isStreaming,
    error,
    finalResponse,
    conversationId,
    startStream,
    startTurnStream,
    abort,
    reset,
  };
}
