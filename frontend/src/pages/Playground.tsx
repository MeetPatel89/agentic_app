import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  ConversationDetail,
  ConversationMessage,
  ConversationTurnRequest,
  NormalizedChatResponse,
  ToolDefinition,
  ToolMode,
} from "../api/types";
import { MetadataPanel } from "../components/MetadataPanel";
import { PlaygroundHeader } from "../components/playground/PlaygroundHeader";
import { SettingsPanel } from "../components/playground/SettingsPanel";
import { ChatMessageList } from "../components/playground/ChatMessageList";
import { ChatInput } from "../components/playground/ChatInput";
import { useStream } from "../hooks/useStream";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function Playground() {
  const [availableProviders, setAvailableProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("anthropic");
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
  const [syncError, setSyncError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(true);

  const [availableTools, setAvailableTools] = useState<ToolDefinition[]>([]);
  const [enabledToolNames, setEnabledToolNames] = useState<string[]>([]);
  const [toolMode, setToolMode] = useState<ToolMode>("off");
  const [isToolRunning, setIsToolRunning] = useState(false);

  const isReasoning = useMemo(() => /^(o\d|gpt-5)/i.test(model), [model]);
  const stream = useStream();
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    api.health().then((res) => setAvailableProviders(res.available_providers)).catch(() => {});
    api.listTools().then((res) => setAvailableTools(res.tools)).catch(() => {});
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
        if (models.length > 0) {
          setModel((current) => models.includes(current) ? current : models[0]!);
        }
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

  const handleToolToggle = useCallback((name: string) => {
    setEnabledToolNames((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );
  }, []);

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
      temperature: isReasoning ? null : temperature,
      max_tokens: Number.isNaN(maxTokens) ? 1024 : maxTokens,
      provider_options: parsedProviderOpts(),
      tool_mode: toolMode,
      tool_names: toolMode === "manual" && enabledToolNames.length > 0 ? enabledToolNames : undefined,
    };

    const toolsActive = toolMode === "auto" || (toolMode === "manual" && enabledToolNames.length > 0);
    if (toolsActive) {
      // Non-streaming fallback when tools are enabled
      setIsToolRunning(true);
      api
        .chatTurn(turnReq)
        .then((res) => {
          if (!conversationId) setConversationId(res.conversation_id);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.content === "") {
              return [...prev.slice(0, -1), { role: "assistant", content: res.response.output_text }];
            }
            return prev;
          });
          setLastResponse(res.response);
          setLastLatency(res.latency_ms);
        })
        .catch((err) => {
          setSyncError(err instanceof Error ? err.message : String(err));
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.content === "") {
              return prev.slice(0, -1);
            }
            return prev;
          });
        })
        .finally(() => setIsToolRunning(false));
    } else {
      stream.startTurnStream(turnReq);
    }
  }, [userInput, conversationId, provider, model, systemPrompt, temperature, maxTokens, parsedProviderOpts, stream, isReasoning, enabledToolNames, toolMode]);

  const handleNewConversation = useCallback(() => {
    stream.reset();
    setConversationId(null);
    setMessages([]);
    setLastResponse(null);
    setLastLatency(null);
    setSyncError(null);
    setSystemPrompt("You are a helpful assistant.");
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

  const isRunning = stream.isStreaming || isToolRunning;
  const hasConversation = conversationId !== null;

  const handleToggleSettings = useCallback(() => setShowSettings((s) => !s), []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <PlaygroundHeader
        conversationId={conversationId}
        showSettings={showSettings}
        onToggleSettings={handleToggleSettings}
        onNewConversation={handleNewConversation}
      />

      {showSettings && (
        <SettingsPanel
          provider={provider}
          model={model}
          availableProviders={availableProviders}
          availableModels={availableModels}
          modelsLoading={modelsLoading}
          systemPrompt={systemPrompt}
          temperature={temperature}
          maxTokens={maxTokens}
          providerOpts={providerOpts}
          hasConversation={hasConversation}
          onProviderChange={setProvider}
          onModelChange={setModel}
          onSystemPromptChange={setSystemPrompt}
          onTemperatureChange={setTemperature}
          onMaxTokensChange={setMaxTokens}
          onProviderOptsChange={setProviderOpts}
          availableTools={availableTools}
          enabledToolNames={enabledToolNames}
          toolMode={toolMode}
          onToolModeChange={setToolMode}
          onToolToggle={handleToolToggle}
        />
      )}

      <ChatMessageList
        messages={messages}
        streamingText={stream.streamingText}
        isStreaming={stream.isStreaming}
        isRunning={isRunning}
      />

      {/* Error display */}
      {(stream.error || syncError) && (
        <div className="error-box" style={{ marginTop: 8 }}>
          {stream.error || syncError}
        </div>
      )}

      {/* Metadata for last response */}
      {lastResponse && <MetadataPanel response={lastResponse} latencyMs={lastLatency} />}

      <ChatInput
        value={userInput}
        isRunning={isRunning}
        onChange={setUserInput}
        onSend={handleSend}
        onAbort={stream.abort}
      />
    </div>
  );
}
