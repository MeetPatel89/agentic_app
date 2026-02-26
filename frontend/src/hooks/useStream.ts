import { useCallback, useRef, useState } from "react";
import type { ChatRequest, NormalizedChatResponse, StreamEvent } from "../api/types";

interface UseStreamReturn {
  streamingText: string;
  isStreaming: boolean;
  error: string | null;
  finalResponse: NormalizedChatResponse | null;
  startStream: (req: ChatRequest) => void;
  abort: () => void;
}

export function useStream(): UseStreamReturn {
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finalResponse, setFinalResponse] = useState<NormalizedChatResponse | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const startStream = useCallback((req: ChatRequest) => {
    abort();
    setStreamingText("");
    setError(null);
    setFinalResponse(null);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(req),
          signal: controller.signal,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(body.detail || `HTTP ${res.status}`);
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
                      setStreamingText((prev) => prev + event.text);
                    }
                    break;
                  case "final":
                    if (event.type === "final") {
                      setFinalResponse(event.response);
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
        setIsStreaming(false);
      }
    })();
  }, [abort]);

  return { streamingText, isStreaming, error, finalResponse, startStream, abort };
}
