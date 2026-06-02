import { apiClient } from "./client";
import type { ActSummary, FeedbackResponse, QueryResponse, ThreadListResponse, ThreadResponse } from "@/types/api";

export async function postQuery(params: {
  question: string;
  act_slug?: string | null;
  language?: string | null;
  as_of_date?: string | null;
}): Promise<QueryResponse> {
  const resp = await apiClient.post<QueryResponse>("/api/v1/query", params);
  return resp.data;
}

export async function postFeedback(params: {
  query_id: string;
  rating: string;
  comment?: string | null;
}): Promise<FeedbackResponse> {
  const resp = await apiClient.post<FeedbackResponse>("/api/v1/feedback", params);
  return resp.data;
}

export async function getActs(): Promise<ActSummary[]> {
  const { data } = await apiClient.get<ActSummary[]>("/api/v1/acts");
  return data;
}

export async function getThread(threadId: string): Promise<ThreadResponse> {
  const { data } = await apiClient.get<ThreadResponse>(`/api/v1/thread/${threadId}`);
  return data;
}

export async function listThreads(limit = 50, offset = 0): Promise<ThreadListResponse> {
  const { data } = await apiClient.get<ThreadListResponse>("/api/v1/threads", {
    params: { limit, offset },
  });
  return data;
}
