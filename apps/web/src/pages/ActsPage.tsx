import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cancelIngestAll, getAdminActs, triggerIngestAll } from "@/api/admin";
import type { AdminActSummary } from "@/types/api";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SourcesRow } from "@/features/SourcesRow";
import { RegisterActModal } from "@/features/RegisterActModal";
import { toast } from "sonner";

export function ActsPage() {
  const [search, setSearch] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const qc = useQueryClient();

  const actsQ = useQuery({
    queryKey: ["admin", "acts"],
    queryFn: getAdminActs,
    refetchInterval: (query) => {
      const acts = query.state.data as AdminActSummary[] | undefined;
      const anyRunning = acts?.some(
        (a: AdminActSummary) =>
          a.last_run_bn?.status === "running" || a.last_run_en?.status === "running",
      );
      return anyRunning ? 3_000 : 30_000;
    },
  });

  const ingestAll = useMutation({
    mutationFn: triggerIngestAll,
    onSuccess: (data) => {
      toast.success(data.message);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to trigger ingestion"),
  });

  const cancelAll = useMutation({
    mutationFn: cancelIngestAll,
    onSuccess: (data) => {
      toast.info(data.message);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to cancel ingestion"),
  });

  const acts = actsQ.data ?? [];
  const anyRunning = acts.some(
    (a) => a.last_run_bn?.status === "running" || a.last_run_en?.status === "running",
  );
  const fullyIngested = acts.filter(
    (a) => a.last_run_bn?.status === "succeeded" && a.last_run_en?.status === "succeeded",
  ).length;
  const totalChunks = acts.reduce(
    (sum, a) =>
      sum + (a.last_run_bn?.chunks_created ?? 0) + (a.last_run_en?.chunks_created ?? 0),
    0,
  );

  const filtered = acts.filter(
    (a) =>
      a.short_name.toLowerCase().includes(search.toLowerCase()) ||
      a.full_name_en.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Acts Registry"
        description="Statutory corpus — ingestion state, coverage, and chunk counts per language."
        actions={
          <>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowRegister(true)}
            >
              <i className="ti ti-plus text-sm" />
              Register Act
            </Button>
            {anyRunning && (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => cancelAll.mutate()}
                disabled={cancelAll.isPending}
              >
                <i className="ti ti-square-x text-sm" />
                Stop all
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => ingestAll.mutate()}
              disabled={ingestAll.isPending || anyRunning}
            >
              <i className={`ti ti-refresh text-sm ${ingestAll.isPending ? "animate-spin" : ""}`} />
              Ingest all
            </Button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Registered Acts
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {actsQ.isLoading ? <Skeleton className="h-7 w-8" /> : acts.length}
          </p>
        </div>
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Fully ingested
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {actsQ.isLoading ? (
              <Skeleton className="h-7 w-10" />
            ) : (
              `${fullyIngested} / ${acts.length}`
            )}
          </p>
        </div>
        <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
            Total chunks
          </p>
          <p className="text-2xl font-bold text-foreground mt-1 tabular-nums">
            {actsQ.isLoading ? (
              <Skeleton className="h-7 w-14" />
            ) : (
              totalChunks.toLocaleString()
            )}
          </p>
        </div>
      </div>

      {/* Temporal limits note */}
      <div className="rounded-xl border border-warning/30 bg-warning/8 px-4 py-3">
        <div className="flex items-start gap-2">
          <i className="ti ti-info-circle text-warning text-base mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            <strong className="text-warning">Temporal limits.</strong> Each Act is indexed from its
            snapshot date. Provisions amended after that date may not be reflected. Consult{" "}
            <span className="font-mono">bdlaws.minlaw.gov.bd</span> directly or re-trigger
            ingestion.
          </p>
        </div>
      </div>

      <div className="relative max-w-sm">
        <i className="ti ti-search absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm pointer-events-none" />
        <Input
          placeholder="Search acts…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8"
        />
      </div>

      <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Act</TableHead>
              <TableHead>Year</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>BN</TableHead>
              <TableHead>EN</TableHead>
              <TableHead>Chunks</TableHead>
              <TableHead>Snapshot</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {actsQ.isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <td colSpan={8} className="px-3 py-2.5">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </TableRow>
              ))}
            {filtered.map((act) => (
              <SourcesRow key={act.id} act={act} />
            ))}
            {!actsQ.isLoading && filtered.length === 0 && (
              <TableRow>
                <td colSpan={8} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <i className="ti ti-books-off text-2xl" />
                    <span className="text-sm">
                      {search ? "No acts match your search" : "No acts registered"}
                    </span>
                  </div>
                </td>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <RegisterActModal open={showRegister} onClose={() => setShowRegister(false)} />
    </div>
  );
}
