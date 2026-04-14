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
  temperature: number | null;
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
  conversation_id?: string;
  run_id?: string;
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

// ── Tool types ────────────────────────────────────────────────────────────

export interface ToolDefinition {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
}

export interface ToolListResponse {
  tools: ToolDefinition[];
}

// ── Conversation types ─────────────────────────────────────────────────────

export type ToolMode = "off" | "auto" | "manual";

export interface ConversationTurnRequest {
  conversation_id?: string;
  provider: string;
  model: string;
  message: string;
  system_prompt?: string;
  temperature: number | null;
  max_tokens: number;
  provider_options: Record<string, unknown>;
  tool_mode?: ToolMode;
  tool_names?: string[];
}

export interface TurnResponse {
  conversation_id: string;
  run_id: string;
  response: NormalizedChatResponse;
  latency_ms: number;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  ordinal: number;
  created_at: string;
  run_id: string | null;
  metadata_json: string | null;
}

export interface ConversationSummary {
  id: string;
  created_at: string;
  updated_at: string;
  title: string | null;
  provider: string;
  model: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  created_at: string;
  updated_at: string;
  title: string | null;
  provider: string;
  model: string;
  system_prompt: string | null;
  config_json: string | null;
  messages: ConversationMessage[];
}

export interface PaginatedConversations {
  items: ConversationSummary[];
  total: number;
  page: number;
  per_page: number;
}

// ── QueryLab (NL-to-SQL) types ─────────────────────────────────────────────

export type SQLDialect = "postgresql" | "tsql" | "mysql" | "sqlite" | "bigquery" | "snowflake";

export interface NL2SQLHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface NL2SQLRequest {
  provider: string;
  model: string;
  natural_language: string;
  dialect: SQLDialect;
  system_prompt?: string;
  schema_context?: string;
  temperature: number | null;
  max_tokens: number;
  sandbox_ddl?: string;
  conversation_history?: NL2SQLHistoryMessage[];
  provider_options: Record<string, unknown>;
}

export type SchemaContextFormat = "compact_ddl" | "structured_catalog" | "concise_notation";

export interface SchemaContextResponse {
  format: SchemaContextFormat;
  schema_text: string;
  table_count: number;
  estimated_tokens: number;
}

export interface SQLValidationResult {
  is_valid: boolean;
  syntax_errors: string[];
  transpiled_sql: string | null;
  sandbox_execution_success: boolean | null;
  sandbox_error: string | null;
}

export interface SQLQuery {
  title: string;
  sql: string;
  explanation: string;
}

export interface NL2SQLResponse {
  generated_sql: string;
  explanation: string;
  queries: SQLQuery[];
  recommended_index: number;
  assumptions: string[];
  dialect: SQLDialect;
  validation: SQLValidationResult;
  usage: Record<string, number | null>;
  run_id: string | null;
  latency_ms: number | null;
  /** Verbatim model completion before parsing (often JSON). */
  raw_llm_output?: string;
}

export interface SQLValidateRequest {
  sql: string;
  dialect: SQLDialect;
  sandbox_ddl?: string;
}

export interface SQLExecuteRequest {
  sql: string;
  dialect: SQLDialect;
  timeout_seconds?: number;
  max_rows?: number;
  read_only?: boolean;
}

export interface SQLExecuteResponse {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
}

export interface QueryLabStreamFinalEvent {
  type?: string;
  generated_sql: string;
  explanation: string;
  queries: SQLQuery[];
  recommended_index: number;
  assumptions: string[];
  dialect: SQLDialect;
  validation: SQLValidationResult;
  usage: Record<string, number | null>;
  run_id: string | null;
  latency_ms: number | null;
  raw_llm_output?: string;
}
