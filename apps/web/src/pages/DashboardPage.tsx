import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getMetrics, getRecentQueries, getHealth } from "@/api/admin";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPercent, formatMs, formatDateTime, truncate } from "@/lib/format";

function HealthItem({ icon, label, value }: { icon: string; label: string; value: string }) {
  const ok = value === "ok";
  return (
    <div className="flex items-center gap-2">
      <i className={`ti ${icon} text-base ${ok ? "text-success" : "text-warning"}`} />
      <span className="text-xs text-muted-foreground">{label}</span>
      <Badge variant={ok ? "success" : "warning"}>{value}</Badge>
    </div>
  );
}

function ConfidenceBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-muted-foreground text-xs">—</span>;
  const v = tier === "HIGH" ? "success" : tier === "MEDIUM" ? "warning" : "destructive";
  return <Badge variant={v as "success" | "warning" | "destructive"}>{tier}</Badge>;
}

export function DashboardPage() {
  const metricsQ = useQuery({
    queryKey: ["admin", "metrics"],
    queryFn: getMetrics,
    refetchInterval: 60_000,
  });
  const queriesQ = useQuery({
    queryKey: ["admin", "queries"],
    queryFn: () => getRecentQueries(10),
    refetchInterval: 30_000,
  });
  const healthQ = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const m = metricsQ.data;
  const h = healthQ.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Dashboard"
        description="Service health, query metrics, and corpus overview."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              void metricsQ.refetch();
              void healthQ.refetch();
              void queriesQ.refetch();
            }}
          >
            <i className="ti ti-refresh text-sm" /> Refresh
          </Button>
        }
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {!m ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[88px]" />)
        ) : (
          <>
            <StatCard icon="ti-messages" label="Queries (24h)" value={m.total_queries} />
            <StatCard
              icon="ti-ban"
              label="Decline rate"
              value={formatPercent(m.decline_rate)}
              hint="advice-seeking"
              tone={m.decline_rate > 0.3 ? "warning" : "default"}
            />
            <StatCard
              icon="ti-bolt"
              label="Cache hit"
              value={formatPercent(m.cache_hit_rate)}
              tone="success"
            />
            <StatCard
              icon="ti-clock"
              label="p95 latency"
              value={formatMs(m.p95_latency_ms)}
            />
          </>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          {/* Health */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <i className="ti ti-activity text-sm text-primary" />
                Service health
              </CardTitle>
            </CardHeader>
            <CardContent>
              {healthQ.isLoading ? (
                <Skeleton className="h-6 w-72" />
              ) : (
                <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
                  <HealthItem icon="ti-wifi" label="API" value={h?.status ?? "—"} />
                  <HealthItem icon="ti-database" label="Database" value={h?.database ?? "—"} />
                  <HealthItem icon="ti-server" label="Redis" value={h?.redis ?? "—"} />
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Environment</span>
                    <Badge variant="secondary">{h?.environment ?? "development"}</Badge>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quality & cost */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <i className="ti ti-chart-dots text-sm text-primary" />
                Quality &amp; cost
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!m ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-[88px]" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard
                    icon="ti-alert-triangle"
                    label="Degraded"
                    value={formatPercent(m.degraded_rate)}
                    tone={m.degraded_rate > 0 ? "warning" : "success"}
                  />
                  <StatCard
                    icon="ti-shield-check"
                    label="HIGH conf."
                    value={m.confidence_breakdown.HIGH}
                    tone="success"
                  />
                  <StatCard
                    icon="ti-coin"
                    label="Daily spend"
                    value={`$${m.daily_spend_usd.toFixed(4)}`}
                    hint="estimated USD"
                  />
                  <StatCard
                    icon="ti-thumb-up"
                    label="Feedback"
                    value={m.feedback_count}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent queries */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <i className="ti ti-history text-sm text-primary" />
                Recent queries
              </CardTitle>
            </CardHeader>
            <CardContent>
              {queriesQ.isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-9" />
                  ))}
                </div>
              ) : (queriesQ.data?.queries.length ?? 0) === 0 ? (
                <p className="text-sm text-muted-foreground py-4">
                  No queries yet — try one in the Playground.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {queriesQ.data!.queries.map((q) => {
                    const threadId = crypto.randomUUID();
                    const replayUrl = `/playground/${threadId}?q=${encodeURIComponent(q.query_text)}`;
                    return (
                      <li key={q.id} className="group flex items-center gap-3 py-2 text-sm">
                        {/* Short query ID */}
                        <span
                          className="font-mono text-[10px] text-muted-foreground/50 shrink-0 w-14 select-all"
                          title={q.id}
                        >
                          {q.id.slice(0, 8)}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-foreground">
                          {truncate(q.query_text, 60)}
                        </span>
                        <span className="text-[11px] uppercase text-muted-foreground font-mono shrink-0">
                          {q.detected_language ?? "—"}
                        </span>
                        <ConfidenceBadge tier={q.confidence_tier} />
                        <div className="flex gap-1 shrink-0">
                          {q.declined && <Badge variant="destructive">declined</Badge>}
                          {q.cached && <Badge variant="accent">cached</Badge>}
                          {q.degraded && <Badge variant="warning">degraded</Badge>}
                        </div>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {formatMs(q.latency_ms)}
                        </span>
                        <span className="w-24 text-right text-xs text-muted-foreground shrink-0">
                          {formatDateTime(q.created_at)}
                        </span>
                        {/* Replay in playground */}
                        <Link
                          to={replayUrl}
                          title="Replay in Playground"
                          className="shrink-0 text-muted-foreground/40 hover:text-primary transition-colors opacity-0 group-hover:opacity-100"
                        >
                          <i className="ti ti-player-play text-sm" />
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <i className="ti ti-player-play text-sm text-primary" />
                Quick actions
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2">
              <Button asChild variant="secondary" className="justify-start gap-2">
                <a href="/playground">
                  <i className="ti ti-message-chatbot text-sm" /> Try a query
                </a>
              </Button>
              <Button asChild variant="secondary" className="justify-start gap-2">
                <a href="/acts">
                  <i className="ti ti-books text-sm" /> Manage Acts
                </a>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
