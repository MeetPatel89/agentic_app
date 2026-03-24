import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  NL2SQLResponse,
  SQLDialect,
  SQLExecuteResponse,
  QueryLabStreamFinalEvent,
} from "../api/types";
import { ConnectionConfig } from "../components/querylab/ConnectionConfig";
import { DialectSelector } from "../components/querylab/DialectSelector";
import { ResultsTable } from "../components/querylab/ResultsTable";
import { SchemaPromptEditor } from "../components/querylab/SchemaPromptEditor";
import { SQLOutput } from "../components/querylab/SQLOutput";
import { ValidationPanel } from "../components/querylab/ValidationPanel";

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

export function QueryLab() {
  // Provider & model
  const [availableProviders, setAvailableProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("gpt-4o-mini");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  // QueryLab settings
  const [dialect, setDialect] = useState<SQLDialect>("postgresql");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [sandboxDDL, setSandboxDDL] = useState("");
  const [temperature, setTemperature] = useState(0.3);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [connectionString, setConnectionString] = useState("");

  // Query state
  const [naturalLanguage, setNaturalLanguage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastResult, setLastResult] = useState<NL2SQLResponse | null>(null);
  const [executeResult, setExecuteResult] = useState<SQLExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Streaming
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const textBufferRef = useRef("");
  const rafIdRef = useRef<number | null>(null);

  const [showSettings, setShowSettings] = useState(true);

  const isReasoning = useMemo(() => /^(o\d|gpt-5)/i.test(model), [model]);

  useEffect(() => {
    api.health().then((res) => setAvailableProviders(res.available_providers)).catch(() => {});
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
          setModel((current) => (models.includes(current) ? current : models[0]!));
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

  const handleGenerate = useCallback(() => {
    const text = naturalLanguage.trim();
    if (!text) return;

    setError(null);
    setLastResult(null);
    setExecuteResult(null);
    setStreamingText("");
    setIsStreaming(true);
    setIsGenerating(true);
    textBufferRef.current = "";

    const controller = new AbortController();
    abortRef.current = controller;

    const body = {
      provider,
      model,
      natural_language: text,
      dialect,
      system_prompt: systemPrompt || undefined,
      temperature: isReasoning ? null : temperature,
      max_tokens: maxTokens,
      sandbox_ddl: sandboxDDL || undefined,
      provider_options: {},
    };

    (async () => {
      try {
        const res = await fetch("/api/querylab/generate/stream", {
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
                const data = JSON.parse(line.slice(6));
                switch (currentEventType) {
                  case "delta":
                    if (data.type === "delta") {
                      textBufferRef.current += data.text;
                      if (rafIdRef.current === null) {
                        rafIdRef.current = requestAnimationFrame(() => {
                          setStreamingText(textBufferRef.current);
                          rafIdRef.current = null;
                        });
                      }
                    }
                    break;
                  case "querylab_final": {
                    const final = data as QueryLabStreamFinalEvent;
                    setLastResult({
                      generated_sql: final.generated_sql,
                      explanation: final.explanation,
                      dialect: final.dialect,
                      validation: final.validation,
                      usage: final.usage,
                      run_id: final.run_id,
                      latency_ms: final.latency_ms,
                    });
                    break;
                  }
                  case "error":
                    if (data.type === "error") {
                      setError(data.message);
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
        setIsGenerating(false);
      }
    })();
  }, [naturalLanguage, provider, model, dialect, systemPrompt, temperature, maxTokens, sandboxDDL, isReasoning]);

  const handleAbort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setIsGenerating(false);
  }, []);

  const handleExecute = useCallback(async () => {
    if (!lastResult?.generated_sql || !connectionString.trim()) return;

    setIsExecuting(true);
    setError(null);
    setExecuteResult(null);
    try {
      const result = await api.executeSQL({
        sql: lastResult.generated_sql,
        dialect,
        connection_string: connectionString,
      });
      setExecuteResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setIsExecuting(false);
    }
  }, [lastResult, connectionString, dialect]);

  const handleValidateOnly = useCallback(async () => {
    if (!lastResult?.generated_sql) return;

    try {
      const validation = await api.validateSQL({
        sql: lastResult.generated_sql,
        dialect,
        sandbox_ddl: sandboxDDL || undefined,
      });
      setLastResult((prev) => (prev ? { ...prev, validation } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    }
  }, [lastResult, dialect, sandboxDDL]);

  const handleReset = useCallback(() => {
    handleAbort();
    setNaturalLanguage("");
    setLastResult(null);
    setExecuteResult(null);
    setError(null);
    setStreamingText("");
    textBufferRef.current = "";
  }, [handleAbort]);

  const isRunning = isGenerating || isExecuting;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>QueryLab</h2>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Natural Language to SQL</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowSettings((s) => !s)}>
            {showSettings ? "Hide Settings" : "Settings"}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleReset}>
            New Query
          </button>
        </div>
      </div>

      {/* Settings */}
      {showSettings && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="form-grid">
            <div className="form-group">
              <label>Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                {ALL_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                    {availableProviders.length > 0 && !availableProviders.includes(p.value) ? " (no key)" : ""}
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

            <DialectSelector value={dialect} onChange={setDialect} />

            <div className="form-group">
              <label>Temperature {isReasoning ? "(N/A — reasoning model)" : `(${temperature})`}</label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.1}
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                disabled={isReasoning}
              />
            </div>

            <div className="form-group">
              <label>Max Tokens</label>
              <input
                type="number"
                min={1}
                max={128000}
                value={maxTokens}
                onChange={(e) => setMaxTokens(parseInt(e.target.value) || 2048)}
              />
            </div>

            <SchemaPromptEditor value={systemPrompt} onChange={setSystemPrompt} />

            <div className="form-group full-width">
              <label>Sandbox DDL (optional — for execution validation)</label>
              <textarea
                rows={4}
                value={sandboxDDL}
                onChange={(e) => setSandboxDDL(e.target.value)}
                placeholder={"CREATE TABLE users (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  email TEXT\n);"}
                style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
              />
            </div>

            <ConnectionConfig connectionString={connectionString} onChange={setConnectionString} />
          </div>
        </div>
      )}

      {/* Query Input */}
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <textarea
          rows={2}
          value={naturalLanguage}
          onChange={(e) => setNaturalLanguage(e.target.value)}
          placeholder="Describe your query in plain English, e.g. 'Show me the top 10 customers by total order value'"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !isRunning) {
              e.preventDefault();
              handleGenerate();
            }
          }}
          style={{ flex: 1, minHeight: 48 }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {isGenerating ? (
            <button className="btn btn-danger" onClick={handleAbort} style={{ height: "100%" }}>
              Stop
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={!naturalLanguage.trim() || isRunning}
              style={{ height: "100%" }}
            >
              Generate SQL
            </button>
          )}
        </div>
      </div>

      {/* SQL Output */}
      <SQLOutput
        sql={lastResult?.generated_sql ?? ""}
        explanation={lastResult?.explanation ?? ""}
        dialect={dialect}
        isStreaming={isStreaming}
        streamingText={streamingText}
      />

      {/* Validation */}
      <ValidationPanel validation={lastResult?.validation ?? null} />

      {/* Action buttons for validated SQL */}
      {lastResult?.generated_sql && !isStreaming && (
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <button className="btn btn-ghost btn-sm" onClick={handleValidateOnly}>
            Re-validate
          </button>
          {connectionString.trim() && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleExecute}
              disabled={isExecuting || !lastResult.validation.is_valid}
            >
              {isExecuting ? "Executing..." : "Execute Against DB"}
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="error-box" style={{ marginTop: 8 }}>
          {error}
        </div>
      )}

      {/* Execution Results */}
      <ResultsTable result={executeResult} />

      {/* Metadata */}
      {lastResult && !isStreaming && (
        <div className="meta-grid" style={{ marginTop: 16 }}>
          {lastResult.latency_ms != null && (
            <div className="meta-item">
              <dt>Latency</dt>
              <dd>{lastResult.latency_ms.toFixed(0)}ms</dd>
            </div>
          )}
          {lastResult.usage.total_tokens != null && (
            <div className="meta-item">
              <dt>Tokens</dt>
              <dd>{lastResult.usage.total_tokens}</dd>
            </div>
          )}
          {lastResult.run_id && (
            <div className="meta-item">
              <dt>Run ID</dt>
              <dd title={lastResult.run_id}>{lastResult.run_id.slice(0, 8)}...</dd>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
