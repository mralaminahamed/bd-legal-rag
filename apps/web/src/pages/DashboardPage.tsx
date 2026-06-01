import { useQuery } from "@tanstack/react-query";
import { getMetrics, getRecentQueries, getHealth } from "@/api/admin";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatPercent, formatMs, formatDateTime, truncate } from "@/lib/format";
import { cn } from "@/lib/utils";

function ServiceDot({ status }: { status: string | undefined }) {
  if (!status) return <span className="w-2 h-2 rounded-full bg-text-5 animate-pulse" />;
  return (
    <span
      className={cn(
        "w-2 h-2 rounded-full",
        status === "ok" ? "bg-score-green" : "bg-score-red"
      )}
    />
  );
}

function HealthRow({
  label,
  status,
}: {
  label: string;
  status: string | undefined;
}) {
  return (
    <div className="flex items-center gap-2">
      <ServiceDot status={status} />
      <span className="text-[12px] text-text-3">{label}</span>
      {status && (
        <span
          className={cn(
            "text-[11px] font-medium",
            status === "ok" ? "text-score-green" : "text-score-red"
          )}
        >
          {status}
        </span>
      )}
    </div>
  );
}

function ConfidenceBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-text-4 text-xs">—</span>;
  const v =
    tier === "HIGH" ? "success" : tier === "MEDIUM" ? "warning" : "destructive";
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
    <div className="flex flex-col min-h-0">
      <PageHeader
        title="Dashboard"
        description="Query quality and service health — last 24 hours"
      />

      <div className="flex-1 overflow-y-auto p-5">
        <div className="space-y-5">

          {/* Service health banner */}
          <div className="bg-surface border border-border rounded-[10px] px-5 py-3.5">
            <div className="flex items-center justify-between">
              <h2 className="text-[12px] font-semibold text-text-3 uppercase tracking-wide">
                Service health
              </h2>
              {h && (
                <span className="text-[11px] text-text-4">auto-refreshes every 30s</span>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
              <HealthRow label="API" status={h?.status} />
              <HealthRow label="Database" status={h?.database} />
              <HealthRow label="Redis" status={h?.redis} />
              {!h && (
                <Skeleton className="h-5 w-48" />
              )}
            </div>
          </div>

          {/* KPI grid */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {m ? (
              <>
                <StatCard
                  title="Queries (24h)"
                  value={m.total_queries}
                  icon="ti-messages"
                  iconClass="text-accent"
                />
                <StatCard
                  title="Decline rate"
                  value={formatPercent(m.decline_rate)}
                  sub="advice-seeking"
                  icon="ti-ban"
                  iconClass="text-score-red"
                />
                <StatCard
                  title="Cache hit rate"
                  value={formatPercent(m.cache_hit_rate)}
                  icon="ti-bolt"
                  iconClass="text-score-amber"
                />
                <StatCard
                  title="p95 latency"
                  value={formatMs(m.p95_latency_ms)}
                  icon="ti-clock"
                  iconClass="text-score-blue"
                />
                <StatCard
                  title="Daily spend"
                  value={`$${m.daily_spend_usd.toFixed(4)}`}
                  sub="estimated USD"
                  icon="ti-coin"
                  iconClass="text-score-amber"
                />
                <StatCard
                  title="Degraded rate"
                  value={formatPercent(m.degraded_rate)}
                  sub="fail-open"
                  icon="ti-alert-triangle"
                  iconClass="text-score-amber"
                />
                <StatCard
                  title="HIGH confidence"
                  value={m.confidence_breakdown.HIGH}
                  icon="ti-shield-check"
                  iconClass="text-score-green"
                />
                <StatCard
                  title="Feedback"
                  value={m.feedback_count}
                  icon="ti-thumb-up"
                  iconClass="text-accent"
                />
              </>
            ) : (
              Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-[88px]" />
              ))
            )}
          </div>

          {/* Recent queries */}
          <div className="bg-surface border border-border rounded-[10px] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-border flex items-center gap-2">
              <i className="ti ti-history text-sm text-accent" />
              <h2 className="text-sm font-bold text-text-1">Recent queries</h2>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Lang</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Flags</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queriesQ.data?.queries.map((q) => (
                  <TableRow key={q.id}>
                    <TableCell className="max-w-xs">
                      <span className="text-[12px] text-text-2 font-medium">
                        {truncate(q.query_text, 75)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-[11px] uppercase font-semibold text-text-3">
                        {q.detected_language ?? "—"}
                      </span>
                    </TableCell>
                    <TableCell>
                      <ConfidenceBadge tier={q.confidence_tier} />
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {q.declined && (
                          <Badge variant="destructive">declined</Badge>
                        )}
                        {q.cached && (
                          <Badge variant="secondary">cached</Badge>
                        )}
                        {q.degraded && (
                          <Badge variant="warning">degraded</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-[12px] tabular-nums text-text-3">
                        {formatMs(q.latency_ms)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-[11px] text-text-4">
                        {formatDateTime(q.created_at)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
                {!queriesQ.data && (
                  <TableRow>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                )}
                {queriesQ.data?.queries.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="py-10 text-center text-text-4 text-sm"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <i className="ti ti-message-off text-2xl" />
                        <span>No queries yet</span>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

        </div>
      </div>
    </div>
  );
}
