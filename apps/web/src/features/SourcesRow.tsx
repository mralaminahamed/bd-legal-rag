import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerIngestAct } from "@/api/admin";
import type { AdminActSummary } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";

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
        className="border-b border-border cursor-pointer hover:bg-muted/50"
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="px-3 py-2 text-sm font-medium">{act.short_name}</td>
        <td className="px-3 py-2 text-sm text-muted-foreground">{act.act_year}</td>
        <td className="px-3 py-2">
          <Badge variant={act.status === "in_force" ? "success" : "secondary"}>
            {act.status}
          </Badge>
        </td>
        <td className="px-3 py-2">
          {act.last_run_bn ? (
            <RunBadge status={act.last_run_bn.status} />
          ) : (
            <span className="text-muted-foreground text-xs">never</span>
          )}
        </td>
        <td className="px-3 py-2">
          {act.last_run_en ? (
            <RunBadge status={act.last_run_en.status} />
          ) : (
            <span className="text-muted-foreground text-xs">never</span>
          )}
        </td>
        <td
          className="px-3 py-2"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            size="sm"
            variant="outline"
            onClick={() => ingest.mutate()}
            disabled={ingest.isPending}
          >
            <RefreshCw
              className={`h-3 w-3 ${ingest.isPending ? "animate-spin" : ""}`}
            />
            Ingest
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-muted/30">
          <td colSpan={6} className="px-6 py-3 text-xs text-muted-foreground">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="font-medium mb-1">Bengali (BN)</div>
                {act.last_run_bn ? (
                  <div>
                    Status: {act.last_run_bn.status} · Started:{" "}
                    {formatDateTime(act.last_run_bn.started_at)}
                    <br />
                    Provisions: {act.last_run_bn.provisions_processed} · Chunks:{" "}
                    {act.last_run_bn.chunks_created}
                    {act.last_run_bn.error && (
                      <div className="text-red-500 mt-1">{act.last_run_bn.error}</div>
                    )}
                  </div>
                ) : (
                  "No runs"
                )}
              </div>
              <div>
                <div className="font-medium mb-1">English (EN)</div>
                {act.last_run_en ? (
                  <div>
                    Status: {act.last_run_en.status} · Started:{" "}
                    {formatDateTime(act.last_run_en.started_at)}
                    <br />
                    Provisions: {act.last_run_en.provisions_processed} · Chunks:{" "}
                    {act.last_run_en.chunks_created}
                    {act.last_run_en.error && (
                      <div className="text-red-500 mt-1">{act.last_run_en.error}</div>
                    )}
                  </div>
                ) : (
                  "No runs"
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
