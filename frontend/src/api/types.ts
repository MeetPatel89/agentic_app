export interface Message {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  name?: string;
  tool_call_id?: string;
}

export interface ChatRequest {
  provider: string;
  model: string;
  messages: Message[];
  temperature: number;
  max_tokens: number;
  provider_options: Record<string, unknown>;
}

export interface UsageInfo {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface NormalizedChatResponse {
  output_text: string;
  finish_reason: string | null;
  provider_response_id: string | null;
  usage: UsageInfo;
  raw: Record<string, unknown>;
}

export interface ChatApiResponse {
  run_id: string;
  response: NormalizedChatResponse;
  latency_ms: number;
}

export interface RunSummary {
  id: string;
  created_at: string;
  provider: string;
  model: string;
  status: string;
  latency_ms: number | null;
  total_tokens: number | null;
  error_message: string | null;
}

export interface RunDetail extends RunSummary {
  request_json: string;
  normalized_response_json: string | null;
  raw_response_json: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  tags: string | null;
  trace_id: string | null;
  parent_run_id: string | null;
}

export interface PaginatedRuns {
  items: RunSummary[];
  total: number;
  page: number;
  per_page: number;
}

export interface StreamDeltaEvent {
  type: "delta";
  text: string;
}

export interface StreamMetaEvent {
  type: "meta";
  provider: string;
  model: string;
}

export interface StreamFinalEvent {
  type: "final";
  response: NormalizedChatResponse;
}

export interface StreamErrorEvent {
  type: "error";
  message: string;
}

export type StreamEvent = StreamDeltaEvent | StreamMetaEvent | StreamFinalEvent | StreamErrorEvent;

export interface HealthResponse {
  status: string;
  available_providers: string[];
}

export interface ProviderModelsResponse {
  provider: string;
  models: string[];
}
