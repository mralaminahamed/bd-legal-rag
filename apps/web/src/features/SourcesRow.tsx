import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cancelIngestAct, triggerIngestAct } from "@/api/admin";
import type { AdminActSummary, IngestionRunSummary } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface SourcesRowProps {
  act: AdminActSummary;
}

function RunBadge({ status }: { status: string }) {
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium bg-primary/10 text-primary border border-primary/20">
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
        running
      </span>
    );
  }
  const v =
    status === "succeeded" ? "success" : status === "failed" ? "destructive" : "secondary";
  return <Badge variant={v as "success" | "destructive" | "secondary"}>{status}</Badge>;
}

function LangStatus({
  run,
  queued,
}: {
  run: IngestionRunSummary | null;
  queued: boolean;
}) {
  const isRunning = queued || run?.status === "running";
  return (
    <td className="px-3 py-3">
      {isRunning ? (
        <RunBadge status="running" />
      ) : run ? (
        <RunBadge status={run.status} />
      ) : (
        <span className="text-muted-foreground text-xs">never</span>
      )}
    </td>
  );
}

function snapshotDate(run: IngestionRunSummary | null | undefined): string {
  if (!run || run.status !== "succeeded" || !run.started_at) return "—";
  return run.started_at.slice(0, 10);
}

function RunBadgeInline({ status }: { status: string }) {
  if (status === "never") return <span className="text-muted-foreground">never</span>;
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1 text-primary font-semibold">
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />running
      </span>
    );
  }
  const color = status === "succeeded" ? "text-success" : status === "failed" ? "text-destructive" : "text-muted-foreground";
  return <span className={color}>{status}</span>;
}

export function SourcesRow({ act, mobile }: SourcesRowProps & { mobile?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [queued, setQueued] = useState(false);
  const qc = useQueryClient();

  const serverHasRun = act.last_run_bn !== null || act.last_run_en !== null;

  useEffect(() => {
    if (queued && serverHasRun) setQueued(false);
  }, [queued, serverHasRun]);

  const ingest = useMutation({
    mutationFn: () => triggerIngestAct(act.slug),
    onSuccess: (data) => {
      toast.success(`Dispatched ${data.task_ids.length} tasks for ${act.short_name}`);
      setQueued(true);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to trigger ingestion"),
  });

  const cancel = useMutation({
    mutationFn: () => cancelIngestAct(act.slug),
    onSuccess: (data) => {
      toast.info(data.message);
      setQueued(false);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to stop ingestion"),
  });

  if (mobile) {
    const chunksTotal = (act.last_run_bn?.chunks_created ?? 0) + (act.last_run_en?.chunks_created ?? 0);
    const isIngested = act.last_run_bn?.status === "succeeded" || act.last_run_en?.status === "succeeded";
    const isRunning = queued || act.last_run_bn?.status === "running" || act.last_run_en?.status === "running";

    return (
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div
          className="p-3 cursor-pointer"
          onClick={() => setExpanded((e) => !e)}
        >
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="text-sm font-medium text-foreground">{act.short_name}</div>
              <div className="text-[11px] text-muted-foreground truncate max-w-[200px]">{act.full_name_en}</div>
            </div>
            <Badge variant={act.status === "in_force" ? "success" : "secondary"}>
              {act.status}
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
            <span className="tabular-nums">{act.act_year}</span>
            <span className="text-border">·</span>
            <span>BN: <RunBadgeInline status={act.last_run_bn?.status ?? "never"} /></span>
            <span className="text-border">·</span>
            <span>EN: <RunBadgeInline status={act.last_run_en?.status ?? "never"} /></span>
            {chunksTotal > 0 && (
              <>
                <span className="text-border">·</span>
                <span>{chunksTotal.toLocaleString()} chunks</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {isIngested && (
              <Button size="sm" variant="ghost" asChild>
                <Link to={`/acts/${act.slug}/read`}><i className="ti ti-book text-sm" /> Read</Link>
              </Button>
            )}
            {isRunning ? (
              <Button size="sm" variant="destructive" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                <i className="ti ti-square-x text-sm" /> Stop
              </Button>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => ingest.mutate()} disabled={ingest.isPending}>
                <i className="ti ti-refresh text-sm" /> Ingest
              </Button>
            )}
          </div>
        </div>
        {expanded && (
          <div className="border-t border-border px-3 py-3 bg-muted/10">
            <div className="grid grid-cols-2 gap-3">
              {([{ lang: "Bengali", run: act.last_run_bn }, { lang: "English", run: act.last_run_en }] as const).map(({ lang, run }) => (
                <div key={lang}>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">{lang}</p>
                  {run ? (
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      <div className="flex items-center gap-1">
                        <RunBadgeInline status={run.status} />
                      </div>
                      <div>Started: {formatDateTime(run.started_at)}</div>
                      <div>{run.provisions_processed} provisions · {run.chunks_created} chunks</div>
                      {run.error && (
                        <div className="text-destructive bg-destructive/10 px-2 py-1 rounded-lg mt-1">{run.error}</div>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs italic text-muted-foreground">No runs yet</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const isRunning =
    queued ||
    act.last_run_bn?.status === "running" ||
    act.last_run_en?.status === "running";

  const chunksTotal =
    (act.last_run_bn?.chunks_created ?? 0) + (act.last_run_en?.chunks_created ?? 0);

  const snapshot = snapshotDate(act.last_run_bn ?? act.last_run_en);

  const isIngested =
    act.last_run_bn?.status === "succeeded" || act.last_run_en?.status === "succeeded";

  return (
    <>
      <tr
        className={cn(
          "border-b border-border cursor-pointer transition-colors",
          expanded ? "bg-muted/20" : "hover:bg-muted/30",
        )}
        onClick={() => setExpanded((e) => !e)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((prev) => !prev);
          }
        }}
        tabIndex={0}
        role="button"
        aria-expanded={expanded}
      >
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <i
              className={cn(
                "ti text-sm text-muted-foreground transition-transform shrink-0",
                expanded ? "ti-chevron-down" : "ti-chevron-right",
              )}
            />
            <div>
              <div className="text-sm font-medium text-foreground">{act.short_name}</div>
              <div className="text-[11px] text-muted-foreground truncate max-w-xs">{act.full_name_en}</div>
            </div>
          </div>
        </td>
        <td className="px-3 py-3">
          <span className="text-sm text-muted-foreground tabular-nums">{act.act_year}</span>
        </td>
        <td className="px-3 py-3">
          <Badge variant={act.status === "in_force" ? "success" : "secondary"}>
            {act.status}
          </Badge>
        </td>
        <LangStatus run={act.last_run_bn} queued={queued} />
        <LangStatus run={act.last_run_en} queued={queued} />
        <td className="px-3 py-3">
          <span className="text-xs tabular-nums text-muted-foreground">
            {chunksTotal > 0 ? chunksTotal.toLocaleString() : "—"}
          </span>
        </td>
        <td className="px-3 py-3">
          <span className="text-xs font-mono text-muted-foreground">{snapshot}</span>
        </td>
        <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center gap-1.5">
            {isIngested && (
              <Button size="sm" variant="ghost" asChild>
                <Link to={`/acts/${act.slug}/read`}>
                  <i className="ti ti-book text-sm" />
                  Read
                </Link>
              </Button>
            )}
            {isRunning ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
              >
                <i className="ti ti-square-x text-sm" />
                Stop
              </Button>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => ingest.mutate()}
                disabled={ingest.isPending}
              >
                <i className="ti ti-refresh text-sm" />
                Ingest
              </Button>
            )}
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-border bg-muted/10">
          <td colSpan={8} className="px-6 py-4">
            <div className="grid grid-cols-2 gap-6">
              {[
                { lang: "Bengali (BN)", run: act.last_run_bn },
                { lang: "English (EN)", run: act.last_run_en },
              ].map(({ lang, run }) => (
                <div key={lang}>
                  <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
                    <i className="ti ti-language text-sm text-primary" />
                    {lang}
                  </div>
                  {run ? (
                    <div className="space-y-1 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Status:</span>
                        <RunBadge status={run.status} />
                      </div>
                      <div className="text-muted-foreground">
                        Started: <span className="text-foreground">{formatDateTime(run.started_at)}</span>
                      </div>
                      <div className="text-muted-foreground">
                        Provisions: <span className="text-foreground tabular-nums">{run.provisions_processed}</span>
                        {" · "}
                        Chunks: <span className="text-foreground tabular-nums">{run.chunks_created}</span>
                      </div>
                      {run.error && (
                        <div className="text-destructive mt-1 bg-destructive/10 px-2 py-1 rounded-lg">
                          {run.error}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">No runs yet</span>
                  )}
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
