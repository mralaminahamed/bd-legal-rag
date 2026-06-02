import { useQuery } from "@tanstack/react-query";
import { getAdminActs } from "@/api/admin";
import { getActs } from "@/api/query";
import { PageHeader } from "@/components/ui/page-header";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { AdminActSummary, ActSummary } from "@/types/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusVariant(status: string): "success" | "warning" | "destructive" | "secondary" {
  if (status === "in_force") return "success";
  if (status === "partially_repealed") return "warning";
  if (status === "repealed") return "destructive";
  return "secondary";
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function coverageDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        "inline-block w-2 h-2 rounded-full shrink-0",
        ok ? "bg-success" : "bg-border",
      )}
    />
  );
}

function snapshotDate(run: AdminActSummary["last_run_bn"]): string {
  if (!run || run.status !== "succeeded" || !run.started_at) return "—";
  return run.started_at.slice(0, 10);
}

// ── Act row ───────────────────────────────────────────────────────────────────

function ActRow({
  summary,
  detail,
}: {
  summary: AdminActSummary;
  detail: ActSummary | undefined;
}) {
  const bnOk = summary.last_run_bn?.status === "succeeded";
  const enOk = summary.last_run_en?.status === "succeeded";
  const asOf = snapshotDate(summary.last_run_bn ?? summary.last_run_en);
  const status = detail?.status ?? summary.status;
  const ministry = detail?.ministry;
  const chunksTotal =
    (summary.last_run_bn?.chunks_created ?? 0) +
    (summary.last_run_en?.chunks_created ?? 0);

  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-3 py-4 border-b border-border last:border-0">
      {/* Act info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-foreground">{summary.short_name}</span>
          <Badge variant={statusVariant(status)} className="capitalize text-[10px]">
            {statusLabel(status)}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5 truncate">{summary.full_name_en}</p>
        {ministry && (
          <p className="text-[11px] text-muted-foreground/70 mt-0.5">{ministry}</p>
        )}
      </div>

      {/* Language coverage */}
      <div className="flex items-center gap-4 shrink-0 text-xs">
        <div className="flex items-center gap-1.5">
          {coverageDot({ ok: bnOk })}
          <span className={cn("font-mono", bnOk ? "text-foreground" : "text-muted-foreground")}>
            BN
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {coverageDot({ ok: enOk })}
          <span className={cn("font-mono", enOk ? "text-foreground" : "text-muted-foreground")}>
            EN
          </span>
        </div>
        <div className="text-muted-foreground w-20 text-right tabular-nums">
          {chunksTotal > 0 ? `${chunksTotal} chunks` : "—"}
        </div>
        <div className="text-muted-foreground w-24 text-right tabular-nums font-mono text-[11px]">
          {asOf}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function CorpusPage() {
  const adminQ = useQuery({
    queryKey: ["admin", "acts"],
    queryFn: getAdminActs,
    refetchInterval: 60_000,
  });

  const publicQ = useQuery({
    queryKey: ["acts"],
    queryFn: getActs,
    staleTime: 300_000,
  });

  const adminActs = adminQ.data ?? [];
  const publicActs = publicQ.data ?? [];

  const totalChunks = adminActs.reduce(
    (sum, a) =>
      sum + (a.last_run_bn?.chunks_created ?? 0) + (a.last_run_en?.chunks_created ?? 0),
    0,
  );
  const ingestedActs = adminActs.filter(
    (a) => a.last_run_bn?.status === "succeeded" || a.last_run_en?.status === "succeeded",
  ).length;
  const fullyIngested = adminActs.filter(
    (a) => a.last_run_bn?.status === "succeeded" && a.last_run_en?.status === "succeeded",
  ).length;

  const detailMap = Object.fromEntries(publicActs.map((a) => [a.slug, a]));

  return (
    <div className="space-y-5">
      <PageHeader
        title="Corpus Coverage"
        description="Registered Acts, language coverage, and temporal snapshot dates."
      />

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Registered Acts
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {adminQ.isLoading ? <Skeleton className="h-7 w-8" /> : adminActs.length}
          </p>
        </div>
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Fully ingested
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {adminQ.isLoading ? <Skeleton className="h-7 w-8" /> : `${fullyIngested} / ${adminActs.length}`}
          </p>
        </div>
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Total chunks
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {adminQ.isLoading ? <Skeleton className="h-7 w-10" /> : totalChunks.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Languages
          </p>
          <p className="text-2xl font-bold text-foreground mt-1">BN · EN</p>
          <p className="text-[11px] text-muted-foreground">Bengali authoritative</p>
        </div>
      </div>

      {/* Disclaimer note */}
      <div className="rounded-xl border border-warning/30 bg-warning/8 px-4 py-3">
        <div className="flex items-start gap-2">
          <i className="ti ti-info-circle text-warning text-base mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            <strong className="text-warning">Temporal limits.</strong> Each Act is indexed from
            the snapshot date shown below. Provisions amended after that date may not be
            reflected. For the current authoritative text, consult{" "}
            <span className="font-mono">bdlaws.minlaw.gov.bd</span> directly or re-trigger
            ingestion.
          </p>
        </div>
      </div>

      {/* Act list */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <i className="ti ti-books text-sm text-primary" />
            Registered Acts
          </CardTitle>
          {/* Column headers */}
          <div className="flex items-center justify-between pt-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            <span>Act</span>
            <div className="flex items-center gap-4 shrink-0">
              <span className="w-8 text-center">BN</span>
              <span className="w-8 text-center">EN</span>
              <span className="w-20 text-right">Chunks</span>
              <span className="w-24 text-right">Snapshot</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-5 pt-0">
          {adminQ.isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : adminActs.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">
              <i className="ti ti-books-off text-2xl mb-2 block" />
              <p className="text-sm">No Acts registered. Run bootstrap first.</p>
              <code className="text-xs mt-2 block">
                python -m app.ingestion.registry bootstrap
              </code>
            </div>
          ) : (
            <div>
              {adminActs
                .slice()
                .sort((a, b) => a.short_name.localeCompare(b.short_name))
                .map((act) => (
                  <ActRow
                    key={act.id}
                    summary={act}
                    detail={detailMap[act.slug]}
                  />
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ingestion status summary */}
      {!adminQ.isLoading && ingestedActs < adminActs.length && (
        <Card>
          <CardContent className="px-5 py-4">
            <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
              <i className="ti ti-refresh text-warning text-base" />
              <span>
                {adminActs.length - ingestedActs} Act(s) have not been ingested yet. Use the{" "}
                <strong className="text-foreground">Acts Registry</strong> page to trigger
                ingestion.
              </span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
