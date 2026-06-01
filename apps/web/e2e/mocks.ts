import type { Page } from "@playwright/test";

export const MOCK_HEALTH = {
  status: "ok",
  service: "bd-legal-rag",
  environment: "development",
  database: "ok",
  redis: "ok",
};

export const MOCK_METRICS = {
  total_queries: 42,
  decline_rate: 0.05,
  confidence_breakdown: { HIGH: 30, MEDIUM: 8, LOW: 4 },
  cache_hit_rate: 0.25,
  degraded_rate: 0.02,
  p95_latency_ms: 1250,
  daily_spend_usd: 0.0032,
  feedback_count: 7,
};

export const MOCK_RECENT_QUERIES = {
  queries: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      query_text: "What is the weekly holiday entitlement?",
      detected_language: "en",
      declined: false,
      confidence_tier: "HIGH",
      cached: false,
      degraded: false,
      latency_ms: 850,
      created_at: new Date().toISOString(),
    },
  ],
  total: 42,
};

export const MOCK_ACTS = [
  {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    slug: "labour-act-2006",
    short_name: "Labour Act 2006",
    full_name_en: "Bangladesh Labour Act",
    act_year: 2006,
    status: "in_force",
    last_run_bn: {
      status: "succeeded",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      provisions_processed: 350,
      chunks_created: 1200,
      error: null,
    },
    last_run_en: null,
  },
];

export const MOCK_LLM_OVERRIDE = {
  provider: "anthropic",
  model: "claude-sonnet-4-6",
  source: "env",
};

export async function setupCommonMocks(page: Page): Promise<void> {
  await page.route("**/health", (route) =>
    route.fulfill({ json: MOCK_HEALTH })
  );
  await page.route("**/api/v1/admin/metrics", (route) =>
    route.fulfill({ json: MOCK_METRICS })
  );
  await page.route("**/api/v1/admin/queries**", (route) =>
    route.fulfill({ json: MOCK_RECENT_QUERIES })
  );
  await page.route("**/api/v1/admin/acts", (route) => {
    if (route.request().method() === "POST") {
      route.fulfill({
        json: { task_ids: ["task-1", "task-2"], message: "dispatched 2 tasks" },
      });
    } else {
      route.fulfill({ json: MOCK_ACTS });
    }
  });
  await page.route("**/api/v1/admin/llm", (route) => {
    const method = route.request().method();
    if (method === "PUT") {
      route.fulfill({ json: { ...MOCK_LLM_OVERRIDE, source: "override" } });
    } else if (method === "DELETE") {
      route.fulfill({ status: 204 });
    } else {
      route.fulfill({ json: MOCK_LLM_OVERRIDE });
    }
  });
  await page.route("**/api/v1/acts", (route) =>
    route.fulfill({
      json: [
        {
          id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          slug: "labour-act-2006",
          short_name: "Labour Act 2006",
          full_name_en: "Bangladesh Labour Act",
          full_name_bn: "বাংলাদেশ শ্রম আইন",
          act_number: "XLII",
          act_year: 2006,
          status: "in_force",
          ministry: null,
        },
      ],
    })
  );
}
