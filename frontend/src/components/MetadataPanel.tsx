import type { NormalizedChatResponse } from "../api/types";

interface Props {
  response: NormalizedChatResponse | null;
  latencyMs?: number | null;
}

export function MetadataPanel({ response, latencyMs }: Props) {
  if (!response) return null;

  const items: { label: string; value: string }[] = [
    { label: "Finish Reason", value: response.finish_reason ?? "—" },
    { label: "Response ID", value: response.provider_response_id ?? "—" },
    { label: "Latency", value: latencyMs != null ? `${Math.round(latencyMs)}ms` : "—" },
    { label: "Prompt Tokens", value: response.usage.prompt_tokens?.toString() ?? "—" },
    { label: "Completion Tokens", value: response.usage.completion_tokens?.toString() ?? "—" },
    { label: "Total Tokens", value: response.usage.total_tokens?.toString() ?? "—" },
  ];

  return (
    <dl className="meta-grid">
      {items.map((item) => (
        <div key={item.label} className="meta-item">
          <dt>{item.label}</dt>
          <dd title={item.value}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
