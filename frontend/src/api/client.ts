import type {
  ChatApiResponse,
  ChatRequest,
  HealthResponse,
  PaginatedRuns,
  ProviderModelsResponse,
  RunDetail,
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
  listModels: (provider: string) =>
    request<ProviderModelsResponse>(`/api/providers/${encodeURIComponent(provider)}/models`),

  chat: (req: ChatRequest) =>
    request<ChatApiResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  listRuns: (page = 1, perPage = 20) =>
    request<PaginatedRuns>(`/api/runs?page=${page}&per_page=${perPage}`),

  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),

  deleteRun: (id: string) =>
    request<{ deleted: string }>(`/api/runs/${id}`, { method: "DELETE" }),
};
