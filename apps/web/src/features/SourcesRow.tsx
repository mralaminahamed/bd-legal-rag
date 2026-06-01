import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerIngestAct } from "@/api/admin";
import type { AdminActSummary } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface SourcesRowProps {
  act: AdminActSummary;
}

function RunBadge({ status }: { status: string }) {
  const v =
    status === "succeeded"
      ? "success"
      : status === "failed"
      ? "destructive"
      : "secondary";
  return <Badge variant={v as "success" | "destructive" | "secondary"}>{status}</Badge>;
}

export function SourcesRow({ act }: SourcesRowProps) {
  const [expanded, setExpanded] = useState(false);
  const qc = useQueryClient();

  const ingest = useMutation({
    mutationFn: () => triggerIngestAct(act.slug),
    onSuccess: (data) => {
      toast.success(`Triggered ${data.task_ids.length} tasks for ${act.short_name}`);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => {
      toast.error("Failed to trigger ingestion");
    },
  });

  return (
    <>
      <tr
        className={cn(
          "border-b border-border cursor-pointer transition-colors",
          expanded ? "bg-page/40" : "hover:bg-page/60"
        )}
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <i
              className={cn(
                "ti text-sm text-text-4 transition-transform shrink-0",
                expanded ? "ti-chevron-down" : "ti-chevron-right"
              )}
            />
            <div>
              <div className="text-sm font-semibold text-text-1">{act.short_name}</div>
              <div className="text-[11px] text-text-4 truncate max-w-xs">{act.full_name_en}</div>
            </div>
          </div>
        </td>
        <td className="px-3 py-3">
          <span className="text-sm text-text-3 tabular-nums">{act.act_year}</span>
        </td>
        <td className="px-3 py-3">
          <Badge variant={act.status === "in_force" ? "success" : "secondary"}>
            {act.status}
          </Badge>
        </td>
        <td className="px-3 py-3">
          {act.last_run_bn ? (
            <RunBadge status={act.last_run_bn.status} />
          ) : (
            <span className="text-text-4 text-xs">never</span>
          )}
        </td>
        <td className="px-3 py-3">
          {act.last_run_en ? (
            <RunBadge status={act.last_run_en.status} />
          ) : (
            <span className="text-text-4 text-xs">never</span>
          )}
        </td>
        <td
          className="px-3 py-3"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            size="sm"
            variant="outline"
            onClick={() => ingest.mutate()}
            disabled={ingest.isPending}
          >
            <i
              className={`ti ti-refresh text-sm ${ingest.isPending ? "animate-spin" : ""}`}
            />
            Ingest
          </Button>
        </td>
      </tr>

      {expanded && (
        <tr className="border-b border-border bg-page/30">
          <td colSpan={6} className="px-6 py-4">
            <div className="grid grid-cols-2 gap-6">
              {[
                { lang: "Bengali (BN)", run: act.last_run_bn },
                { lang: "English (EN)", run: act.last_run_en },
              ].map(({ lang, run }) => (
                <div key={lang}>
                  <div className="text-[12px] font-semibold text-text-3 mb-2 flex items-center gap-1.5">
                    <i className="ti ti-language text-sm text-accent" />
                    {lang}
                  </div>
                  {run ? (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-[12px]">
                        <span className="text-text-4">Status:</span>
                        <RunBadge status={run.status} />
                      </div>
                      <div className="text-[12px] text-text-4">
                        Started: <span className="text-text-2">{formatDateTime(run.started_at)}</span>
                      </div>
                      <div className="text-[12px] text-text-4">
                        Provisions: <span className="text-text-2 tabular-nums">{run.provisions_processed}</span>
                        {" · "}
                        Chunks: <span className="text-text-2 tabular-nums">{run.chunks_created}</span>
                      </div>
                      {run.error && (
                        <div className="text-[12px] text-score-red mt-1 bg-score-red-bg px-2 py-1 rounded">
                          {run.error}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-[12px] text-text-4 italic">No runs yet</span>
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
