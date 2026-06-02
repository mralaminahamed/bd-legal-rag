export interface QueryResponse {
  query_id: string;
  answer: string;
  citations: string[];
  disclaimer: string;
  disclaimer_version: string;
  confidence: "HIGH" | "MEDIUM" | "LOW" | null;
  cached: boolean;
  degraded: boolean;
  declined: boolean;
  detected_language: string;
  as_of_date: string | null;
}

export interface FeedbackResponse {
  feedback_id: string;
  query_id: string;
  rating: string;
}

export interface ThreadMessage {
  id: string;
  question: string;
  answer: string | null;
  disclaimer: string | null;
  declined: boolean;
  cached: boolean;
  degraded: boolean;
  confidence_tier: "HIGH" | "MEDIUM" | "LOW" | null;
  detected_language: string | null;
  created_at: string;
}

export interface ThreadResponse {
  thread_id: string;
  messages: ThreadMessage[];
}

export interface ActSummary {
  id: string;
  slug: string;
  short_name: string;
  full_name_en: string;
  full_name_bn: string;
  act_number: string;
  act_year: number;
  status: string;
  ministry: string | null;
}

export interface ProvisionTreeNode {
  id: string;
  kind: string;
  number: string;
  title: string | null;
  sort_path: string;
  children: ProvisionTreeNode[];
}

export interface ActStructure {
  act: ActSummary;
  tree: ProvisionTreeNode[];
}

export interface RevisionDetail {
  language: string;
  translation_status: string;
  text: string;
  effective_from: string;
  effective_to: string | null;
  source_url: string;
}

export interface SectionDetail {
  provision_id: string;
  act_slug: string;
  kind: string;
  number: string;
  title: string | null;
  hierarchy_path: string;
  revisions: RevisionDetail[];
  disclaimer: string;
}

export interface IngestionRunSummary {
  status: "running" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  provisions_processed: number;
  chunks_created: number;
  error: string | null;
}

export interface AdminActSummary {
  id: string;
  slug: string;
  short_name: string;
  full_name_en: string;
  act_year: number;
  status: string;
  last_run_bn: IngestionRunSummary | null;
  last_run_en: IngestionRunSummary | null;
}

export interface LLMOverrideResponse {
  provider: string;
  model: string;
  source: "override" | "env";
}

export interface ConfidenceBreakdown {
  HIGH: number;
  MEDIUM: number;
  LOW: number;
}

export interface MetricsResponse {
  total_queries: number;
  decline_rate: number;
  confidence_breakdown: ConfidenceBreakdown;
  cache_hit_rate: number;
  degraded_rate: number;
  p95_latency_ms: number | null;
  daily_spend_usd: number;
  feedback_count: number;
}

export interface RecentQuery {
  id: string;
  query_text: string;
  detected_language: string | null;
  declined: boolean;
  confidence_tier: string | null;
  cached: boolean;
  degraded: boolean;
  latency_ms: number | null;
  created_at: string;
}

export interface RecentQueriesResponse {
  queries: RecentQuery[];
  total: number;
}

export interface IngestionTriggerResponse {
  task_ids: string[];
  message: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  environment: string;
  database: "ok" | "unavailable";
  redis: "ok" | "unavailable";
}

export type StreamEventType = "token" | "final";

export interface StreamEvent {
  type: StreamEventType;
  text: string | null;
  answer: string | null;
  citations: string[] | null;
  disclaimer: string | null;
  cached: boolean;
  degraded: boolean;
  declined: boolean;
}
