import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getMetrics, getRecentQueries, getHealth } from "@/api/admin";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPercent, formatMs, formatDateTime, truncate } from "@/lib/format";
import { cn } from "@/lib/utils";

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({
  icon,
  label,
  value,
  hint,
  tone = "default",
}: {
  icon: string;
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "success" | "warning" | "destructive";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : tone === "destructive"
          ? "text-destructive"
          : "text-primary";

  return (
    <div className="rounded-xl ring-1 ring-foreground/8 bg-card p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <i className={`ti ${icon} text-sm ${toneClass} opacity-60`} />
      </div>
      <div className={cn("text-xl font-bold tabular-nums", toneClass === "text-primary" ? "text-foreground" : toneClass)}>
        {value}
      </div>
      {hint && (
        <p className="text-[10px] text-muted-foreground mt-0.5">{hint}</p>
      )}
    </div>
  );
}

// ── Health dot ────────────────────────────────────────────────────────────────

function HealthDot({ label, status }: { label: string; status: string }) {
  const ok = status === "ok";
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", ok ? "bg-success" : "bg-warning")} />
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn("text-xs font-medium", ok ? "text-success" : "text-warning")}>{status}</span>
    </div>
  );
}

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-muted-foreground text-xs">—</span>;
  const v = tier === "HIGH" ? "success" : tier === "MEDIUM" ? "warning" : "destructive";
  return <Badge variant={v as "success" | "warning" | "destructive"}>{tier}</Badge>;
}

// ── Main page ─────────────────────────────────────────────────────────────────

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

  function refetchAll() {
    void metricsQ.refetch();
    void healthQ.refetch();
    void queriesQ.refetch();
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Service health and query metrics</p>
        </div>
        <Button variant="ghost" size="sm" onClick={refetchAll}>
          <i className="ti ti-refresh text-sm" />
          Refresh
        </Button>
      </div>

      {/* KPI grid — 8 cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {!m ? (
          Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[84px] rounded-xl" />)
        ) : (
          <>
            <KpiCard icon="ti-messages" label="Queries (24h)" value={m.total_queries} />
            <KpiCard
              icon="ti-ban"
              label="Decline rate"
              value={formatPercent(m.decline_rate)}
              hint="low recall floor"
              tone={m.decline_rate > 0.3 ? "warning" : "default"}
            />
            <KpiCard
              icon="ti-bolt"
              label="Cache hit"
              value={formatPercent(m.cache_hit_rate)}
              tone="success"
            />
            <KpiCard icon="ti-clock" label="p95 latency" value={formatMs(m.p95_latency_ms)} />
            <KpiCard
              icon="ti-alert-triangle"
              label="Degraded"
              value={formatPercent(m.degraded_rate)}
              tone={m.degraded_rate > 0 ? "warning" : "success"}
            />
            <KpiCard
              icon="ti-shield-check"
              label="HIGH conf."
              value={m.confidence_breakdown.HIGH}
              tone="success"
            />
            <KpiCard
              icon="ti-coin"
              label="Daily spend"
              value={`$${m.daily_spend_usd.toFixed(4)}`}
              hint="estimated USD"
            />
            <KpiCard icon="ti-thumb-up" label="Feedback" value={m.feedback_count} />
          </>
        )}
      </div>

      {/* Service health + Quick actions */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Service health */}
        <div className="lg:col-span-2 rounded-xl ring-1 ring-foreground/8 bg-card px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2">
              <i className="ti ti-activity text-sm text-primary" />
              Service health
            </h2>
            {h && (
              <Badge variant={h.status === "ok" ? "success" : "warning"}>
                {h.status}
              </Badge>
            )}
          </div>
          {healthQ.isLoading ? (
            <Skeleton className="h-5 w-64" />
          ) : (
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <HealthDot label="API" status={h?.status ?? "—"} />
              <HealthDot label="Database" status={h?.database ?? "—"} />
              <HealthDot label="Redis" status={h?.redis ?? "—"} />
              <div className="flex items-center gap-1.5">
                <i className="ti ti-server text-xs text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Env</span>
                <span className="text-xs font-medium text-foreground">{h?.environment ?? "development"}</span>
              </div>
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="rounded-xl ring-1 ring-foreground/8 bg-card px-5 py-4">
          <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2 mb-3">
            <i className="ti ti-player-play text-sm text-primary" />
            Quick actions
          </h2>
          <div className="space-y-1.5">
            {[
              { to: "/playground", icon: "ti-message-chatbot", label: "New conversation" },
              { to: "/acts", icon: "ti-books", label: "Acts Registry" },
              { to: "/threads", icon: "ti-messages", label: "View conversations" },
            ].map(({ to, icon, label }) => (
              <Link
                key={to}
                to={to}
                className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <i className={`ti ${icon} text-sm shrink-0`} />
                {label}
                <i className="ti ti-chevron-right text-xs ml-auto opacity-40" />
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Recent queries */}
      <div className="rounded-xl ring-1 ring-foreground/8 bg-card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2">
            <i className="ti ti-history text-sm text-primary" />
            Recent queries
          </h2>
          <Link
            to="/threads"
            className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1"
          >
            All threads <i className="ti ti-arrow-right text-[10px]" />
          </Link>
        </div>

        {queriesQ.isLoading ? (
          <div className="space-y-px p-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 rounded-lg" />
            ))}
          </div>
        ) : (queriesQ.data?.queries.length ?? 0) === 0 ? (
          <div className="flex flex-col items-center py-12 text-center text-muted-foreground">
            <i className="ti ti-messages-off text-2xl mb-2" />
            <p className="text-sm">No queries yet — try one in the Playground</p>
          </div>
        ) : (
          <ul>
            {queriesQ.data!.queries.map((q, i) => {
              const threadId = crypto.randomUUID();
              const replayUrl = `/playground/${threadId}?q=${encodeURIComponent(q.query_text)}`;
              return (
                <li
                  key={q.id}
                  className={cn(
                    "group flex items-center gap-3 px-5 py-2.5 hover:bg-muted/40 transition-colors",
                    i < (queriesQ.data!.queries.length - 1) && "border-b border-border/60",
                  )}
                >
                  <span className="font-mono text-[10px] text-muted-foreground/40 shrink-0 w-14 select-all" title={q.id}>
                    {q.id.slice(0, 8)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                    {truncate(q.query_text, 65)}
                  </span>
                  <span className="text-[11px] uppercase font-mono text-muted-foreground shrink-0">
                    {q.detected_language ?? "—"}
                  </span>
                  <ConfidenceBadge tier={q.confidence_tier} />
                  <div className="flex gap-1 shrink-0">
                    {q.declined && <Badge variant="destructive">declined</Badge>}
                    {q.cached && <Badge variant="accent">cached</Badge>}
                    {q.degraded && <Badge variant="warning">degraded</Badge>}
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
                    {formatMs(q.latency_ms)}
                  </span>
                  <span className="w-28 text-right text-xs text-muted-foreground shrink-0 tabular-nums">
                    {formatDateTime(q.created_at)}
                  </span>
                  <Link
                    to={replayUrl}
                    title="Open in Playground"
                    className="shrink-0 text-muted-foreground/30 hover:text-primary transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <i className="ti ti-player-play text-sm" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
