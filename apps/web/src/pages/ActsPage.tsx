import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAdminActs, triggerIngestAll } from "@/api/admin";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SourcesRow } from "@/features/SourcesRow";
import { RegisterActModal } from "@/features/RegisterActModal";
import { toast } from "sonner";
import { RefreshCw, Plus } from "lucide-react";

export function ActsPage() {
  const [search, setSearch] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const qc = useQueryClient();

  const actsQ = useQuery({
    queryKey: ["admin", "acts"],
    queryFn: getAdminActs,
    refetchInterval: 60_000,
  });

  const ingestAll = useMutation({
    mutationFn: triggerIngestAll,
    onSuccess: (data) => {
      toast.success(data.message);
      void qc.invalidateQueries({ queryKey: ["admin", "acts"] });
    },
    onError: () => toast.error("Failed to trigger ingestion"),
  });

  const filtered = (actsQ.data ?? []).filter(
    (a) =>
      a.short_name.toLowerCase().includes(search.toLowerCase()) ||
      a.full_name_en.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Acts Registry"
        description="Statutory corpus — ingestion state per language"
        action={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowRegister(true)}
            >
              <Plus className="h-4 w-4" />
              Register Act
            </Button>
            <Button
              size="sm"
              onClick={() => ingestAll.mutate()}
              disabled={ingestAll.isPending}
            >
              <RefreshCw
                className={`h-4 w-4 ${ingestAll.isPending ? "animate-spin" : ""}`}
              />
              Ingest all
            </Button>
          </div>
        }
      />

      <div className="p-6 space-y-4">
        <Input
          placeholder="Search acts…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />

        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Act</TableHead>
                <TableHead>Year</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>BN run</TableHead>
                <TableHead>EN run</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {actsQ.isLoading &&
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <td colSpan={6} className="px-3 py-2">
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </TableRow>
                ))}
              {filtered.map((act) => (
                <SourcesRow key={act.id} act={act} />
              ))}
              {!actsQ.isLoading && filtered.length === 0 && (
                <TableRow>
                  <td
                    colSpan={6}
                    className="px-3 py-8 text-center text-sm text-muted-foreground"
                  >
                    {search ? "No acts match your search" : "No acts registered"}
                  </td>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <RegisterActModal
        open={showRegister}
        onClose={() => setShowRegister(false)}
      />
    </div>
  );
}
