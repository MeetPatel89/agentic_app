import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  NL2SQLHistoryMessage,
  NL2SQLResponse,
  SQLDialect,
  SQLExecuteResponse,
  SQLQuery,
  QueryLabStreamFinalEvent,
} from "../api/types";
import { DialectSelector } from "../components/querylab/DialectSelector";
import { ResultsTable } from "../components/querylab/ResultsTable";
import { SchemaPromptEditor } from "../components/querylab/SchemaPromptEditor";
import { SQLOutput } from "../components/querylab/SQLOutput";
import { ValidationPanel } from "../components/querylab/ValidationPanel";

// ---------------------------------------------------------------------------
// Sub-components for multi-query display
// ---------------------------------------------------------------------------

interface QueryVariantTabsProps {
  queries: SQLQuery[];
  selectedIndex: number;
  recommendedIndex: number;
  onSelect?: (index: number) => void;
  readOnly?: boolean;
}

function QueryVariantTabs({ queries, selectedIndex, recommendedIndex, onSelect, readOnly }: QueryVariantTabsProps) {
  return (
    <div style={{ display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap" }}>
      {queries.map((q, i) => (
        <button
          key={i}
          className={`btn btn-sm ${i === selectedIndex ? "btn-primary" : "btn-ghost"}`}
          onClick={readOnly ? undefined : () => onSelect?.(i)}
          style={{ cursor: readOnly ? "default" : "pointer", fontSize: 12 }}
          title={q.explanation}
        >
          {q.title}
          {i === recommendedIndex && (
            <span style={{ marginLeft: 4, fontSize: 10, opacity: 0.7 }}>recommended</span>
          )}
        </button>
      ))}
    </div>
  );
}

function AssumptionsList({ assumptions }: { assumptions: string[] }) {
  if (!assumptions || assumptions.length === 0) return null;
  return (
    <div
      style={{
        marginTop: 8,
        padding: "8px 12px",
        background: "var(--bg-input)",
        borderRadius: "var(--radius)",
        fontSize: 12,
        color: "var(--text-muted)",
      }}
    >
      <strong style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>Assumptions</strong>
      <ul style={{ margin: "4px 0 0", paddingLeft: 16 }}>
        {assumptions.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
    </div>
  );
}

type QueryLabViewTab = "sql" | "raw";

function RawLLMOutput({ text, isStreaming }: { text: string; isStreaming: boolean }) {
  const display =
    isStreaming ? "Waiting for model response…" : text.trim() ? text : "No raw text was returned.";
  const canCopy = !isStreaming && text.trim().length > 0;

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <label style={{ margin: 0, fontSize: 13 }}>Raw model output</label>
        {canCopy && (
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => void navigator.clipboard.writeText(text)}>
            Copy
          </button>
        )}
      </div>
      <pre
        className={isStreaming ? "output-panel streaming" : "output-panel"}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          margin: 0,
          wordBreak: "break-word",
        }}
      >
        <code style={isStreaming ? { color: "var(--text-muted)" } : undefined}>{display}</code>
        {isStreaming && <span className="cursor-blink" />}
      </pre>
    </div>
  );
}

interface QueryLabAssistantPanelProps {
  dialect: SQLDialect;
  isStreaming: boolean;
  result: NL2SQLResponse | null;
  selectedQueryIndex: number;
  onSelectQuery?: (index: number) => void;
  variantTabsReadOnly?: boolean;
}

function QueryLabAssistantPanel({
  dialect,
  isStreaming,
  result,
  selectedQueryIndex,
  onSelectQuery,
  variantTabsReadOnly = false,
}: QueryLabAssistantPanelProps) {
  const [tab, setTab] = useState<QueryLabViewTab>("sql");

  const activeQuery =
    result != null
      ? result.queries[selectedQueryIndex] ?? {
          title: "Query",
          sql: result.generated_sql,
          explanation: result.explanation,
        }
      : null;

  const showVariants = !isStreaming && result != null && result.queries.length > 1;

  return (
    <>
      <div style={{ display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-muted)", marginRight: 4 }}>View:</span>
        <button
          type="button"
          className={`btn btn-sm ${tab === "sql" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("sql")}
        >
          SQL
        </button>
        <button
          type="button"
          className={`btn btn-sm ${tab === "raw" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setTab("raw")}
          disabled={isStreaming}
        >
          Raw response
        </button>
      </div>

      {tab === "sql" ? (
        <>
          {showVariants && (
            <QueryVariantTabs
              queries={result!.queries}
              selectedIndex={selectedQueryIndex}
              recommendedIndex={result!.recommended_index}
              onSelect={variantTabsReadOnly ? undefined : onSelectQuery}
              readOnly={variantTabsReadOnly}
            />
          )}
          <SQLOutput
            sql={activeQuery?.sql ?? ""}
            explanation={activeQuery?.explanation ?? ""}
            dialect={dialect}
            isStreaming={isStreaming}
          />
        </>
      ) : (
        <RawLLMOutput text={result?.raw_llm_output ?? ""} isStreaming={isStreaming} />
      )}

      {!isStreaming && result && <AssumptionsList assumptions={result.assumptions} />}
    </>
  );
}

// ---------------------------------------------------------------------------

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

interface CompletedTurn {
  userQuery: string;
  result: NL2SQLResponse;
  executeResult: SQLExecuteResponse | null;
  selectedQueryIndex: number;
}

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

  // Execution mode
  const [mode, setMode] = useState<"generate" | "generate_and_execute">("generate");

  // Conversation turns
  const [turns, setTurns] = useState<CompletedTurn[]>([]);

  // Current turn state
  const [naturalLanguage, setNaturalLanguage] = useState("");
  const [currentQuery, setCurrentQuery] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastResult, setLastResult] = useState<NL2SQLResponse | null>(null);
  const [executeResult, setExecuteResult] = useState<SQLExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Multi-query selection
  const [selectedQueryIndex, setSelectedQueryIndex] = useState(0);

  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const [showSettings, setShowSettings] = useState(true);
  const threadEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const isReasoning = useMemo(() => /^(o\d|gpt-5)/i.test(model), [model]);

  // Derive conversation_history from completed turns for the API
  const conversationHistory = useMemo<NL2SQLHistoryMessage[]>(
    () =>
      turns.flatMap((t) => {
        const query = t.result.queries[t.selectedQueryIndex] ?? {
          sql: t.result.generated_sql,
          explanation: t.result.explanation,
        };
        const assistantContent = query.explanation
          ? `${query.sql}\n\n${query.explanation}`
          : query.sql;
        return [
          { role: "user" as const, content: t.userQuery },
          { role: "assistant" as const, content: assistantContent },
        ];
      }),
    [turns],
  );

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

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, isStreaming, lastResult, executeResult]);

  const executeSQL = useCallback(async (sql: string) => {
    if (!sql) return;

    setIsExecuting(true);
    setError(null);
    setExecuteResult(null);
    try {
      const result = await api.executeSQL({ sql, dialect, read_only: true });
      setExecuteResult(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Execution failed";
      if (message.includes("Read-only execution mode") || message.includes("exactly one SQL statement")) {
        setError(`Execution blocked for safety: ${message}`);
      } else {
        setError(message);
      }
    } finally {
      setIsExecuting(false);
    }
  }, [dialect]);

  const handleGenerate = useCallback(() => {
    const text = naturalLanguage.trim();
    if (!text) return;

    // Commit the previous turn to the thread if there's an outstanding result
    if (lastResult && currentQuery) {
      setTurns((prev) => [
        ...prev,
        { userQuery: currentQuery, result: lastResult, executeResult, selectedQueryIndex },
      ]);
    }

    // Clear input and current-turn state
    setNaturalLanguage("");
    setCurrentQuery(text);
    setError(null);
    setLastResult(null);
    setExecuteResult(null);
    setSelectedQueryIndex(0);
    setIsStreaming(true);
    setIsGenerating(true);

    const controller = new AbortController();
    abortRef.current = controller;

    // Build history: completed turns + uncommitted current turn (if any)
    const historyForRequest = lastResult && currentQuery
      ? [
          ...conversationHistory,
          {
            role: "user" as const,
            content: currentQuery,
          },
          {
            role: "assistant" as const,
            content: lastResult.explanation
              ? `${lastResult.generated_sql}\n\n${lastResult.explanation}`
              : lastResult.generated_sql,
          },
        ]
      : conversationHistory;

    const body = {
      provider,
      model,
      natural_language: text,
      dialect,
      system_prompt: systemPrompt || undefined,
      temperature: isReasoning ? null : temperature,
      max_tokens: maxTokens,
      sandbox_ddl: sandboxDDL || undefined,
      conversation_history: historyForRequest.length > 0 ? historyForRequest : undefined,
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
                  case "querylab_final": {
                    const final = data as QueryLabStreamFinalEvent;
                    const result: NL2SQLResponse = {
                      generated_sql: final.generated_sql,
                      explanation: final.explanation,
                      queries: final.queries ?? [],
                      recommended_index: final.recommended_index ?? 0,
                      assumptions: final.assumptions ?? [],
                      dialect: final.dialect,
                      validation: final.validation,
                      usage: final.usage,
                      run_id: final.run_id,
                      latency_ms: final.latency_ms,
                      raw_llm_output: final.raw_llm_output ?? "",
                    };
                    setLastResult(result);
                    setSelectedQueryIndex(result.recommended_index);

                    if (
                      mode === "generate_and_execute" &&
                      final.validation.is_valid &&
                      final.generated_sql
                    ) {
                      executeSQL(final.generated_sql);
                    }
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
        setIsStreaming(false);
        setIsGenerating(false);
        inputRef.current?.focus();
      }
    })();
  }, [naturalLanguage, currentQuery, lastResult, executeResult, selectedQueryIndex, provider, model, dialect, systemPrompt, temperature, maxTokens, sandboxDDL, conversationHistory, isReasoning, mode, executeSQL]);

  const handleAbort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setIsGenerating(false);
  }, []);

  // Derive the currently active query for the in-progress turn
  const activeQuery: SQLQuery | null = useMemo(() => {
    if (!lastResult) return null;
    return lastResult.queries[selectedQueryIndex] ?? {
      title: "Query",
      sql: lastResult.generated_sql,
      explanation: lastResult.explanation,
    };
  }, [lastResult, selectedQueryIndex]);

  const handleSelectQuery = useCallback((index: number) => {
    setSelectedQueryIndex(index);
  }, []);

  const handleExecute = useCallback(async () => {
    const sql = activeQuery?.sql;
    if (!sql) return;
    await executeSQL(sql);
  }, [activeQuery, executeSQL]);

  const handleValidateOnly = useCallback(async () => {
    const sql = activeQuery?.sql;
    if (!sql) return;

    try {
      const validation = await api.validateSQL({
        sql,
        dialect,
        sandbox_ddl: sandboxDDL || undefined,
      });
      setLastResult((prev) => (prev ? { ...prev, validation } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    }
  }, [activeQuery, dialect, sandboxDDL]);

  const handleReset = useCallback(() => {
    handleAbort();
    setNaturalLanguage("");
    setCurrentQuery(null);
    setLastResult(null);
    setExecuteResult(null);
    setError(null);
    setTurns([]);
  }, [handleAbort]);

  const isRunning = isGenerating || isExecuting;
  const hasPriorTurns = turns.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>QueryLab</h2>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Natural Language to SQL</span>
          {(hasPriorTurns || lastResult) && (
            <span style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg-muted)", padding: "2px 8px", borderRadius: 8 }}>
              {turns.length + (lastResult ? 1 : 0)} turn{turns.length + (lastResult ? 1 : 0) !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowSettings((s) => !s)}>
            {showSettings ? "Hide Settings" : "Settings"}
          </button>
          {(hasPriorTurns || lastResult) && (
            <button className="btn btn-ghost btn-sm" onClick={handleReset}>
              New Conversation
            </button>
          )}
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
                value={Number.isNaN(maxTokens) ? "" : maxTokens}
                onChange={(e) => {
                  const val = e.target.value;
                  setMaxTokens(val === "" ? NaN : parseInt(val));
                }}
                onBlur={() => {
                  if (Number.isNaN(maxTokens) || maxTokens < 1) setMaxTokens(2048);
                }}
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
          </div>
        </div>
      )}

      {/* Mode Toggle */}
      <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
        <label style={{ fontSize: 12, color: "var(--text-muted)", marginRight: 4 }}>Mode:</label>
        <button
          className={`btn btn-sm ${mode === "generate" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setMode("generate")}
        >
          Generate Only
        </button>
        <button
          className={`btn btn-sm ${mode === "generate_and_execute" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setMode("generate_and_execute")}
          title="Generate SQL and execute automatically against the configured database"
        >
          Generate &amp; Execute
        </button>
      </div>

      {/* Conversation Thread */}
      <div style={{ flex: 1, overflowY: "auto", marginBottom: 12 }}>
        {/* Prior completed turns */}
        {turns.map((turn, i) => (
          <div key={i} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, fontWeight: 500 }}>You</div>
            <div style={{ marginBottom: 8, padding: "8px 12px", background: "var(--bg-muted)", borderRadius: 8 }}>
              {turn.userQuery}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, fontWeight: 500 }}>Response</div>
            <QueryLabAssistantPanel
              dialect={dialect}
              isStreaming={false}
              result={turn.result}
              selectedQueryIndex={turn.selectedQueryIndex}
              variantTabsReadOnly
            />
            <ValidationPanel validation={turn.result.validation} />
            <ResultsTable result={turn.executeResult} />
          </div>
        ))}

        {/* Current / in-progress turn */}
        {currentQuery && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, fontWeight: 500 }}>You</div>
            <div style={{ marginBottom: 8, padding: "8px 12px", background: "var(--bg-muted)", borderRadius: 8 }}>
              {currentQuery}
            </div>

            {(isStreaming || lastResult) && (
              <>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4, fontWeight: 500 }}>Response</div>
                <QueryLabAssistantPanel
                  key={`${turns.length}-${currentQuery}`}
                  dialect={dialect}
                  isStreaming={isStreaming}
                  result={lastResult}
                  selectedQueryIndex={selectedQueryIndex}
                  onSelectQuery={handleSelectQuery}
                />
              </>
            )}

            <ValidationPanel validation={lastResult?.validation ?? null} />

            {/* Action buttons for current turn */}
            {lastResult?.generated_sql && !isStreaming && (
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="btn btn-ghost btn-sm" onClick={handleValidateOnly}>
                  Re-validate
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleExecute}
                  disabled={isExecuting || !lastResult.validation.is_valid}
                >
                  {isExecuting ? "Executing..." : "Execute Against DB"}
                </button>
              </div>
            )}

            {error && (
              <div className="error-box" style={{ marginTop: 8 }}>
                {error}
              </div>
            )}

            <ResultsTable result={executeResult} />

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
        )}

        <div ref={threadEndRef} />
      </div>

      {/* Input — pinned at bottom */}
      <div style={{ display: "flex", gap: 8 }}>
        <textarea
          ref={inputRef}
          rows={2}
          value={naturalLanguage}
          onChange={(e) => setNaturalLanguage(e.target.value)}
          placeholder={
            hasPriorTurns || lastResult
              ? "Refine your query, e.g. 'add a WHERE clause for active users' or 'sort by date descending'"
              : "Describe your query in plain English, e.g. 'Show me the top 10 customers by total order value'"
          }
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
              {mode === "generate_and_execute" ? "Generate & Execute" : "Generate SQL"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
