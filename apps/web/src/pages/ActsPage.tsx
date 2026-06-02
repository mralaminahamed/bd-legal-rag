import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAdminActs, triggerIngestAll } from "@/api/admin";
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
    // Poll every 3s while any act is running; every 30s otherwise
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
      // Immediately refetch, then fast-poll kicks in via refetchInterval
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to trigger ingestion"),
  });

  const filtered = (actsQ.data ?? []).filter(
    (a) =>
      a.short_name.toLowerCase().includes(search.toLowerCase()) ||
      a.full_name_en.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Acts Registry"
        description="Statutory corpus — ingestion state per language."
        actions={
          <>
            <Button size="sm" variant="ghost" asChild>
              <Link to="/corpus">
                <i className="ti ti-timeline text-sm" />
                Coverage
              </Link>
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setShowRegister(true)}
            >
              <i className="ti ti-plus text-sm" />
              Register Act
            </Button>
            <Button
              size="sm"
              onClick={() => ingestAll.mutate()}
              disabled={ingestAll.isPending}
            >
              <i className={`ti ti-refresh text-sm ${ingestAll.isPending ? "animate-spin" : ""}`} />
              Ingest all
            </Button>
          </>
        }
      />

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
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {actsQ.isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <td colSpan={6} className="px-3 py-2.5">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </TableRow>
              ))}
            {filtered.map((act) => (
              <SourcesRow key={act.id} act={act} />
            ))}
            {!actsQ.isLoading && filtered.length === 0 && (
              <TableRow>
                <td colSpan={6} className="px-3 py-12 text-center">
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
