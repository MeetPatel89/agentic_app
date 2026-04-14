import type {
  ChatApiResponse,
  ChatRequest,
  ConversationDetail,
  ConversationTurnRequest,
  HealthResponse,
  NL2SQLRequest,
  NL2SQLResponse,
  SchemaContextFormat,
  SchemaContextResponse,
  PaginatedConversations,
  PaginatedRuns,
  ProviderModelsResponse,
  RunDetail,
  SQLExecuteRequest,
  SQLExecuteResponse,
  SQLValidateRequest,
  SQLValidationResult,
  ToolListResponse,
  TurnResponse,
} from "./types";

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  listTools: () => request<ToolListResponse>("/api/tools"),
  listModels: (provider: string) =>
    request<ProviderModelsResponse>(`/api/providers/${encodeURIComponent(provider)}/models`),

  // Legacy single-shot
  chat: (req: ChatRequest) =>
    request<ChatApiResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // Turn-based conversation
  chatTurn: (req: ConversationTurnRequest) =>
    request<TurnResponse>("/api/chat/turn", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // Runs
  listRuns: (page = 1, perPage = 20) =>
    request<PaginatedRuns>(`/api/runs?page=${page}&per_page=${perPage}`),

  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),

  deleteRun: (id: string) =>
    request<{ deleted: string }>(`/api/runs/${id}`, { method: "DELETE" }),

  // Conversations
  listConversations: (page = 1, perPage = 20) =>
    request<PaginatedConversations>(`/api/conversations?page=${page}&per_page=${perPage}`),

  getConversation: (id: string) =>
    request<ConversationDetail>(`/api/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<{ deleted: string }>(`/api/conversations/${id}`, { method: "DELETE" }),

  updateConversation: (id: string, body: { title?: string }) =>
    request<{ id: string; title: string }>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // QueryLab (NL-to-SQL)
  generateSQL: (req: NL2SQLRequest) =>
    request<NL2SQLResponse>("/api/querylab/generate", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  validateSQL: (req: SQLValidateRequest) =>
    request<SQLValidationResult>("/api/querylab/validate", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  executeSQL: (req: SQLExecuteRequest) =>
    request<SQLExecuteResponse>("/api/querylab/execute", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // Dev DB — schema context (requires DEV_DB_TOOLS_ENABLED on the backend)
  fetchSchemaContext: (params?: {
    format?: SchemaContextFormat;
    tables?: string[];
    includeForeignKeys?: boolean;
  }) => {
    const search = new URLSearchParams();
    if (params?.format) search.set("format", params.format);
    if (params?.tables && params.tables.length > 0) {
      search.set("tables", params.tables.join(","));
    }
    if (params?.includeForeignKeys === false) {
      search.set("include_foreign_keys", "false");
    }
    const qs = search.toString();
    return request<SchemaContextResponse>(
      `/api/dev/db/schema-context${qs ? `?${qs}` : ""}`,
    );
  },
};
