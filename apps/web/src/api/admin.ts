import { adminClient } from "./client";
import type {
  AdminActSummary,
  HealthResponse,
  IngestionTriggerResponse,
  LLMOverrideResponse,
  MetricsResponse,
  RecentQueriesResponse,
} from "@/types/api";

export async function getAdminActs(): Promise<AdminActSummary[]> {
  const { data } = await adminClient.get<AdminActSummary[]>("/api/v1/admin/acts");
  return data;
}

export async function triggerIngestAll(): Promise<IngestionTriggerResponse> {
  const { data } = await adminClient.post<IngestionTriggerResponse>(
    "/api/v1/admin/acts/ingest"
  );
  return data;
}

export async function triggerIngestAct(slug: string): Promise<IngestionTriggerResponse> {
  const { data } = await adminClient.post<IngestionTriggerResponse>(
    `/api/v1/admin/acts/${slug}/ingest`
  );
  return data;
}

export async function getLLMOverride(): Promise<LLMOverrideResponse> {
  const { data } = await adminClient.get<LLMOverrideResponse>("/api/v1/admin/llm");
  return data;
}

export async function setLLMOverride(params: {
  provider: string;
  model: string;
}): Promise<LLMOverrideResponse> {
  const { data } = await adminClient.put<LLMOverrideResponse>(
    "/api/v1/admin/llm",
    params
  );
  return data;
}

export async function clearLLMOverride(): Promise<void> {
  await adminClient.delete("/api/v1/admin/llm");
}

export async function getMetrics(): Promise<MetricsResponse> {
  const { data } = await adminClient.get<MetricsResponse>("/api/v1/admin/metrics");
  return data;
}

export async function getRecentQueries(limit = 50): Promise<RecentQueriesResponse> {
  const { data } = await adminClient.get<RecentQueriesResponse>(
    `/api/v1/admin/queries?limit=${limit}`
  );
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await adminClient.get<HealthResponse>("/health");
  return data;
}
