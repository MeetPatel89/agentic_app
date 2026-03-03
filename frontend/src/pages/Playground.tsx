import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationTurnRequest,
  NormalizedChatResponse,
} from "../api/types";
import { StreamOutput } from "../components/StreamOutput";
import { MetadataPanel } from "../components/MetadataPanel";
import { useStream } from "../hooks/useStream";

const ALL_PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google_gemini", label: "Google Gemini" },
  { value: "mistral", label: "Mistral" },
  { value: "groq", label: "Groq" },
  { value: "together", label: "Together" },
  { value: "azure_openai", label: "Azure OpenAI" },
  { value: "local_openai_compatible", label: "Local (OpenAI-compatible)" },
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function Playground() {
  const [availableProviders, setAvailableProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o-mini");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful assistant.");
  const [userInput, setUserInput] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [providerOpts, setProviderOpts] = useState("");

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<NormalizedChatResponse | null>(null);
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(true);

  const stream = useStream();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, stream.streamingText, scrollToBottom]);

  useEffect(() => {
    api.health().then((h) => setAvailableProviders(h.available_providers)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setModelsLoading(true);
    api
      .listModels(provider)
      .then((res) => {
        if (cancelled) return;
        const models = res.models ?? [];
        setAvailableModels(models);
        setModel((current) =>
          models.length > 0 && !models.includes(current) ? models[0] : current,
        );
      })
      .catch(() => {
        if (!cancelled) setAvailableModels([]);
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [provider]);

  // Capture conversation_id from stream final event
  useEffect(() => {
    if (stream.conversationId && !conversationId) {
      setConversationId(stream.conversationId);
    }
  }, [stream.conversationId, conversationId]);

  // When stream completes, add assistant message to history
  useEffect(() => {
    if (!stream.isStreaming && stream.finalResponse && stream.streamingText) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content === "") {
          return [...prev.slice(0, -1), { role: "assistant", content: stream.finalResponse!.output_text }];
        }
        return prev;
      });
      setLastResponse(stream.finalResponse);
    }
  }, [stream.isStreaming, stream.finalResponse, stream.streamingText]);

  const parsedProviderOpts = useCallback((): Record<string, unknown> => {
    if (!providerOpts.trim()) return {};
    try {
      return JSON.parse(providerOpts);
    } catch {
      return {};
    }
  }, [providerOpts]);

  const handleSend = useCallback(() => {
    const text = userInput.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setUserInput("");
    setSyncError(null);
    setLastResponse(null);
    setLastLatency(null);

    const turnReq: ConversationTurnRequest = {
      conversation_id: conversationId ?? undefined,
      provider,
      model,
      message: text,
      system_prompt: conversationId ? undefined : systemPrompt || undefined,
      temperature,
      max_tokens: maxTokens,
      provider_options: parsedProviderOpts(),
    };

    stream.startTurnStream(turnReq);
  }, [userInput, conversationId, provider, model, systemPrompt, temperature, maxTokens, parsedProviderOpts, stream]);

  const handleSendSync = useCallback(() => {
    const text = userInput.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setUserInput("");
    setSyncError(null);
    setLastResponse(null);
    setLastLatency(null);
    setSyncLoading(true);

    const turnReq: ConversationTurnRequest = {
      conversation_id: conversationId ?? undefined,
      provider,
      model,
      message: text,
      system_prompt: conversationId ? undefined : systemPrompt || undefined,
      temperature,
      max_tokens: maxTokens,
      provider_options: parsedProviderOpts(),
    };

    api
      .chatTurn(turnReq)
      .then((res) => {
        setConversationId(res.conversation_id);
        setMessages((prev) => [...prev, { role: "assistant", content: res.response.output_text }]);
        setLastResponse(res.response);
        setLastLatency(res.latency_ms);
      })
      .catch((err) => setSyncError(err instanceof Error ? err.message : "Request failed"))
      .finally(() => setSyncLoading(false));
  }, [userInput, conversationId, provider, model, systemPrompt, temperature, maxTokens, parsedProviderOpts]);

  const handleNewConversation = useCallback(() => {
    stream.abort();
    setConversationId(null);
    setMessages([]);
    setLastResponse(null);
    setLastLatency(null);
    setSyncError(null);
    setShowSettings(true);
  }, [stream]);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const detail: ConversationDetail = await api.getConversation(id);
      setConversationId(detail.id);
      setProvider(detail.provider);
      setModel(detail.model);
      if (detail.system_prompt) setSystemPrompt(detail.system_prompt);
      setMessages(
        detail.messages
          .filter((m: ConversationMessage) => m.role === "user" || m.role === "assistant")
          .map((m: ConversationMessage) => ({ role: m.role as "user" | "assistant", content: m.content })),
      );
      setShowSettings(false);
    } catch {
      /* ignore */
    }
  }, []);

  // Load conversation from ?conversation= query param
  useEffect(() => {
    const convParam = searchParams.get("conversation");
    if (convParam && convParam !== conversationId) {
      loadConversation(convParam);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, conversationId, loadConversation]);

  const isRunning = stream.isStreaming || syncLoading;
  const hasConversation = conversationId !== null;

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="section-header">
        <h2>Playground</h2>
        <div className="flex gap-8" style={{ alignItems: "center" }}>
          {hasConversation && (
            <span style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              {conversationId!.slice(0, 8)}…
            </span>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => setShowSettings((s) => !s)}>
            Settings {showSettings ? "▲" : "▼"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleNewConversation}>
            New Chat
          </button>
        </div>
      </div>

      {showSettings && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="form-grid">
            <div className="form-group">
              <label>Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={hasConversation}
              >
                {ALL_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                    {availableProviders.length > 0 && !availableProviders.includes(p.value)
                      ? " (no key)"
                      : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Model</label>
              {availableModels.length > 0 ? (
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={modelsLoading || hasConversation}
                >
                  {availableModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={modelsLoading ? "Loading models..." : "Enter model name"}
                  disabled={hasConversation}
                />
              )}
            </div>

            <div className="form-group full-width">
              <label>System Prompt</label>
              <textarea
                rows={2}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                disabled={hasConversation}
              />
            </div>

            <div className="form-group">
              <label>Temperature ({temperature})</label>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label>Max Tokens</label>
              <input
                type="number"
                min={1}
                max={128000}
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1024)}
              />
            </div>

            <div className="form-group full-width">
              <label>Provider Options (JSON)</label>
              <textarea
                rows={2}
                value={providerOpts}
                onChange={(e) => setProviderOpts(e.target.value)}
                placeholder='{"top_p": 0.9}'
              />
            </div>
          </div>
        </div>
      )}

      {/* Chat messages area */}
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
        <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
          {messages.length === 0 && !isRunning && (
            <div style={{ color: "var(--text-muted)", textAlign: "center", padding: "40px 0" }}>
              Send a message to start a conversation.
            </div>
          )}

          {messages.map((msg, i) => {
            const isLastAssistant =
              msg.role === "assistant" && i === messages.length - 1;
            const isStreamingThis = isLastAssistant && stream.isStreaming;
            const displayContent =
              isStreamingThis
                ? stream.streamingText
                : msg.content;

            return (
              <div
                key={i}
                style={{
                  marginBottom: 16,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: msg.role === "user" ? "flex-end" : "flex-start",
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
                  {msg.role}
                </div>
                <div
                  style={{
                    maxWidth: "85%",
                    padding: "10px 14px",
                    borderRadius: 12,
                    background:
                      msg.role === "user"
                        ? "var(--accent)"
                        : "var(--bg-elevated, var(--card-bg))",
                    color:
                      msg.role === "user"
                        ? "#fff"
                        : "var(--text-primary)",
                  }}
                >
                  {msg.role === "assistant" ? (
                    <StreamOutput
                      text={displayContent}
                      isStreaming={isStreamingThis}
                    />
                  ) : (
                    <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Error display */}
      {(stream.error || syncError) && (
        <div className="error-box" style={{ marginTop: 8 }}>
          {stream.error || syncError}
        </div>
      )}

      {/* Metadata for last response */}
      {lastResponse && <MetadataPanel response={lastResponse} latencyMs={lastLatency} />}

      {/* Input area */}
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <textarea
          rows={2}
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          style={{
            flex: 1,
            resize: "none",
            borderRadius: 8,
            padding: "10px 14px",
            border: "1px solid var(--border)",
            background: "var(--bg-primary, var(--card-bg))",
            color: "var(--text-primary)",
            fontFamily: "inherit",
            fontSize: 14,
          }}
          disabled={isRunning}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 4, justifyContent: "center" }}>
          <button
            className="btn btn-primary"
            disabled={isRunning || !userInput.trim()}
            onClick={handleSend}
            title="Send (streaming)"
          >
            {isRunning ? "…" : "Send"}
          </button>
          {isRunning && (
            <button className="btn btn-ghost btn-sm" onClick={stream.abort}>
              Stop
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
