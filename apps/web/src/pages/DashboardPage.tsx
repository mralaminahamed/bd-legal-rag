import { useQuery } from "@tanstack/react-query";
import { getMetrics, getRecentQueries, getHealth } from "@/api/admin";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatPercent, formatMs, formatDateTime, truncate } from "@/lib/format";

function HealthBadge({ status }: { status: string }) {
  return (
    <Badge variant={status === "ok" ? "success" : "destructive"}>
      {status}
    </Badge>
  );
}

function ConfidenceBadge({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-muted-foreground">—</span>;
  const v =
    tier === "HIGH" ? "success" : tier === "MEDIUM" ? "warning" : "destructive";
  return (
    <Badge variant={v as "success" | "warning" | "destructive"}>{tier}</Badge>
  );
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

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Dashboard"
        description="Query quality and service health — last 24 hours"
      />

      <div className="p-6 space-y-6">
        {/* Health row */}
        <div className="flex items-center gap-3 text-sm">
          <span className="font-medium">Service:</span>
          {healthQ.data ? (
            <>
              <HealthBadge status={healthQ.data.status} />
              <span className="text-muted-foreground">
                DB <HealthBadge status={healthQ.data.database} /> · Redis{" "}
                <HealthBadge status={healthQ.data.redis} />
              </span>
            </>
          ) : (
            <Skeleton className="h-5 w-32" />
          )}
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {m ? (
            <>
              <StatCard title="Total queries (24h)" value={m.total_queries} />
              <StatCard
                title="Decline rate"
                value={formatPercent(m.decline_rate)}
                sub="advice-seeking queries"
              />
              <StatCard
                title="Cache hit rate"
                value={formatPercent(m.cache_hit_rate)}
              />
              <StatCard
                title="p95 latency"
                value={formatMs(m.p95_latency_ms)}
              />
              <StatCard
                title="Daily spend"
                value={`$${m.daily_spend_usd.toFixed(4)}`}
                sub="estimated USD"
              />
              <StatCard
                title="Degraded"
                value={formatPercent(m.degraded_rate)}
                sub="fail-open rate"
              />
              <StatCard
                title="HIGH confidence"
                value={m.confidence_breakdown.HIGH}
              />
              <StatCard title="Feedback" value={m.feedback_count} />
            </>
          ) : (
            Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))
          )}
        </div>

        {/* Recent queries */}
        <Card>
          <CardHeader>
            <CardTitle>Recent queries</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
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
                      <span className="text-xs">{truncate(q.query_text, 80)}</span>
                    </TableCell>
                    <TableCell className="text-xs uppercase">
                      {q.detected_language ?? "—"}
                    </TableCell>
                    <TableCell>
                      <ConfidenceBadge tier={q.confidence_tier} />
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {q.declined && <Badge variant="destructive">declined</Badge>}
                        {q.cached && <Badge variant="secondary">cached</Badge>}
                        {q.degraded && <Badge variant="warning">degraded</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs">{formatMs(q.latency_ms)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDateTime(q.created_at)}
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
                      className="text-center text-muted-foreground text-sm py-8"
                    >
                      No queries yet
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
