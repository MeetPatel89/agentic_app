import { memo, useMemo } from "react";
import type { ToolDefinition, ToolMode } from "../../api/types";
import { ToolSettingsSection } from "./ToolSettingsSection";

const REASONING_MODEL_RE = /^(o\d|gpt-5)/i;

function isReasoningModel(model: string): boolean {
  return REASONING_MODEL_RE.test(model);
}

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

interface Props {
  provider: string;
  model: string;
  availableProviders: string[];
  availableModels: string[];
  modelsLoading: boolean;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  providerOpts: string;
  hasConversation: boolean;
  availableTools: ToolDefinition[];
  enabledToolNames: string[];
  toolMode: ToolMode;
  onProviderChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onSystemPromptChange: (value: string) => void;
  onTemperatureChange: (value: number) => void;
  onMaxTokensChange: (value: number) => void;
  onProviderOptsChange: (value: string) => void;
  onToolModeChange: (value: ToolMode) => void;
  onToolToggle: (name: string) => void;
}

export const SettingsPanel = memo(function SettingsPanel({
  provider,
  model,
  availableProviders,
  availableModels,
  modelsLoading,
  systemPrompt,
  temperature,
  maxTokens,
  providerOpts,
  hasConversation,
  availableTools,
  enabledToolNames,
  toolMode,
  onProviderChange,
  onModelChange,
  onSystemPromptChange,
  onTemperatureChange,
  onMaxTokensChange,
  onProviderOptsChange,
  onToolModeChange,
  onToolToggle,
}: Props) {
  const reasoning = useMemo(() => isReasoningModel(model), [model]);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="form-grid">
        <div className="form-group">
          <label>Provider</label>
          <select
            value={provider}
            onChange={(e) => onProviderChange(e.target.value)}
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
              onChange={(e) => onModelChange(e.target.value)}
              disabled={modelsLoading}
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
              onChange={(e) => onModelChange(e.target.value)}
              placeholder={modelsLoading ? "Loading models..." : "Enter model name"}
            />
          )}
        </div>

        <div className="form-group full-width">
          <label>System Prompt</label>
          <textarea
            rows={2}
            value={systemPrompt}
            onChange={(e) => onSystemPromptChange(e.target.value)}
            disabled={hasConversation}
          />
        </div>

        <div className="form-group">
          <label>
            Temperature {reasoning ? "(N/A — reasoning model)" : `(${temperature})`}
          </label>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => onTemperatureChange(parseFloat(e.target.value))}
            disabled={reasoning}
          />
        </div>

        <div className="form-group">
          <label>Max Tokens</label>
          <input
            type="number"
            min={1}
            max={128000}
            value={maxTokens}
            onChange={(e) => onMaxTokensChange(parseInt(e.target.value) || 1024)}
          />
        </div>

        <div className="form-group full-width">
          <label>Provider Options (JSON)</label>
          <textarea
            rows={2}
            value={providerOpts}
            onChange={(e) => onProviderOptsChange(e.target.value)}
            placeholder='{"top_p": 0.9}'
          />
        </div>

        <ToolSettingsSection
          availableTools={availableTools}
          enabledToolNames={enabledToolNames}
          toolMode={toolMode}
          onToolModeChange={onToolModeChange}
          onToolToggle={onToolToggle}
        />
      </div>
    </div>
  );
});
