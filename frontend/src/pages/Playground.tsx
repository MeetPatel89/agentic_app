import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { ChatRequest, NormalizedChatResponse } from "../api/types";
import { MetadataPanel } from "../components/MetadataPanel";
import { StreamOutput } from "../components/StreamOutput";
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

export function Playground() {
  const [availableProviders, setAvailableProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o-mini");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful assistant.");
  const [userPrompt, setUserPrompt] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [providerOpts, setProviderOpts] = useState("");
  const [useStreaming, setUseStreaming] = useState(true);

  const [syncResponse, setSyncResponse] = useState<NormalizedChatResponse | null>(null);
  const [syncText, setSyncText] = useState("");
  const [syncLatency, setSyncLatency] = useState<number | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const stream = useStream();

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
          models.length > 0 && !models.includes(current) ? models[0] : current
        );
      })
      .catch(() => {
        if (!cancelled) {
          setAvailableModels([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setModelsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const buildRequest = useCallback((): ChatRequest => {
    const messages = [];
    if (systemPrompt.trim()) {
      messages.push({ role: "system" as const, content: systemPrompt });
    }
    messages.push({ role: "user" as const, content: userPrompt });

    let parsedOpts: Record<string, unknown> = {};
    if (providerOpts.trim()) {
      try {
        parsedOpts = JSON.parse(providerOpts);
      } catch {
        /* ignore parse errors */
      }
    }

    return {
      provider,
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
      provider_options: parsedOpts,
    };
  }, [provider, model, systemPrompt, userPrompt, temperature, maxTokens, providerOpts]);

  const handleRun = useCallback(() => {
    const req = buildRequest();
    if (!userPrompt.trim()) return;

    if (useStreaming) {
      setSyncResponse(null);
      setSyncText("");
      setSyncLatency(null);
      setSyncError(null);
      stream.startStream(req);
    } else {
      stream.abort();
      setSyncResponse(null);
      setSyncText("");
      setSyncLatency(null);
      setSyncError(null);
      setSyncLoading(true);

      const start = performance.now();
      api
        .chat(req)
        .then((res) => {
          setSyncResponse(res.response);
          setSyncText(res.response.output_text);
          setSyncLatency(res.latency_ms ?? performance.now() - start);
        })
        .catch((err) => setSyncError(err instanceof Error ? err.message : "Request failed"))
        .finally(() => setSyncLoading(false));
    }
  }, [buildRequest, userPrompt, useStreaming, stream]);

  const displayText = useStreaming ? stream.streamingText : syncText;
  const displayError = useStreaming ? stream.error : syncError;
  const displayResponse = useStreaming ? stream.finalResponse : syncResponse;
  const isRunning = useStreaming ? stream.isStreaming : syncLoading;

  return (
    <div>
      <div className="section-header">
        <h2>Playground</h2>
        <label style={{ display: "flex", alignItems: "center", gap: 8, textTransform: "none" }}>
          <input
            type="checkbox"
            checked={useStreaming}
            onChange={(e) => setUseStreaming(e.target.checked)}
          />
          <span style={{ fontSize: 13 }}>Stream</span>
        </label>
      </div>

      <div className="card">
        <div className="form-grid">
          <div className="form-group">
            <label>Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
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
              <select value={model} onChange={(e) => setModel(e.target.value)} disabled={modelsLoading}>
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
              />
            )}
          </div>

          <div className="form-group full-width">
            <label>System Prompt</label>
            <textarea
              rows={2}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
            />
          </div>

          <div className="form-group full-width">
            <label>User Prompt</label>
            <textarea
              rows={4}
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              placeholder="Type your prompt here..."
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

        <div className="mt-16 flex gap-8">
          <button
            className="btn btn-primary"
            disabled={isRunning || !userPrompt.trim()}
            onClick={handleRun}
          >
            {isRunning ? "Running..." : "Run"}
          </button>
          {isRunning && useStreaming && (
            <button className="btn btn-ghost" onClick={stream.abort}>
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="mt-24">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Output</h3>
        <StreamOutput text={displayText} isStreaming={stream.isStreaming && useStreaming} />
        {displayError && <div className="error-box">{displayError}</div>}
        <MetadataPanel response={displayResponse} latencyMs={syncLatency} />
        {displayResponse && Object.keys(displayResponse.raw).length > 0 && (
          <details className="mt-16">
            <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--text-muted)" }}>
              Raw Response
            </summary>
            <pre className="json-block mt-16">
              {JSON.stringify(displayResponse.raw, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
