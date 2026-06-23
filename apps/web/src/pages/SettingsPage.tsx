import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getProviderConfig, switchEmbedding } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/ui/page-header";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ThemePicker } from "@/components/ThemePicker";

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Ollama (Local)",
  anthropic: "Anthropic",
  openai: "OpenAI",
  gemini: "Google Gemini",
  openrouter: "OpenRouter",
  groq: "Groq",
  ollama_cloud: "Ollama Cloud",
  cohere: "Cohere",
};

const PROVIDER_ICONS: Record<string, string> = {
  ollama: "ti-server",
  anthropic: "ti-brand-anthropic",
  openai: "ti-brain",
  gemini: "ti-sparkles",
  openrouter: "ti-route",
  groq: "ti-bolt",
  ollama_cloud: "ti-cloud",
  cohere: "ti-vector",
};

export function SettingsPage() {
  const configQ = useQuery({
    queryKey: ["admin", "config"],
    queryFn: getProviderConfig,
  });
  const queryClient = useQueryClient();
  const [switchResult, setSwitchResult] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<{ provider: string; model: string; dimensions: number } | null>(null);

  const switchMutation = useMutation({
    mutationFn: switchEmbedding,
    onSuccess: (data) => {
      setSwitchResult(data.message);
      queryClient.invalidateQueries({ queryKey: ["admin", "config"] });
      setTimeout(() => setSwitchResult(null), 5000);
    },
    onError: (err: Error) => {
      setSwitchResult(err.message || "Failed to switch embedding provider.");
      setTimeout(() => setSwitchResult(null), 5000);
    },
  });

  const c = configQ.data;

  return (
    <div className="space-y-5">
      {/* Header */}
      <PageHeader
        title="Settings"
        description="Provider configuration overview"
      />

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {!c ? configQ.isError ? (
          <div className="col-span-full rounded-xl ring-1 ring-foreground/10 bg-card p-8 flex flex-col items-center text-center">
            <i className="ti ti-alert-circle text-3xl text-destructive mb-3" />
            <p className="text-sm font-semibold text-foreground mb-1">Failed to load config</p>
            <p className="text-xs text-muted-foreground mb-4">Check your connection and try again.</p>
            <Button variant="outline" size="sm" onClick={() => configQ.refetch()}>
              <i className="ti ti-refresh text-sm" />
              Retry
            </Button>
          </div>
        ) : (
          <>
            <Skeleton className="h-[84px] rounded-xl" />
            <Skeleton className="h-[84px] rounded-xl" />
            <Skeleton className="h-[84px] rounded-xl" />
          </>
        ) : (
          <>
            <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                Default Provider
              </span>
              <div className="text-xl font-bold text-foreground mt-1 capitalize">
                {c.default_provider.replaceAll("_", " ")}
              </div>
            </div>
            <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                Embedding Model
              </span>
              <div className="text-xl font-bold font-mono text-foreground mt-1">
                {c.embed_model}
              </div>
            </div>
            <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-4">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                Embed Dimensions
              </span>
              <div className="text-xl font-bold text-foreground mt-1">
                {c.embed_dimensions}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Provider table */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2">
            <i className="ti ti-settings text-sm text-primary" />
            Providers
          </h2>
        </div>

        {configQ.isLoading ? (
          <div className="space-y-px p-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Model</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(c?.providers ?? {}).map(
                ([key, info]) => (
                  <TableRow key={key}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <i
                          className={cn(
                            "ti text-sm shrink-0",
                            PROVIDER_ICONS[key] ?? "ti-circle",
                            info.configured
                              ? "text-primary"
                              : "text-muted-foreground/40",
                          )}
                        />
                        <span className="font-medium text-foreground">
                          {PROVIDER_LABELS[key] ?? key}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <span
                          className={cn(
                            "w-1.5 h-1.5 rounded-full shrink-0",
                            info.configured ? "bg-success" : "bg-muted-foreground/30",
                          )}
                        />
                        <span
                          className={cn(
                            "text-xs font-medium",
                            info.configured
                              ? "text-success"
                              : "text-muted-foreground",
                          )}
                        >
                          {info.configured ? "Configured" : "Not configured"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {info.model}
                    </TableCell>
                  </TableRow>
                ),
              )}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Theme */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2">
            <i className="ti ti-palette text-sm text-primary" />
            Theme
          </h2>
        </div>
        <div className="p-5">
          <ThemePicker />
        </div>
      </div>

      {/* Embedding Provider */}
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-[13px] font-semibold text-foreground flex items-center gap-2">
            <i className="ti ti-vector text-sm text-primary" />
            Embedding Provider
          </h2>
        </div>
        <div className="p-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              {
                key: "cohere",
                model: "embed-multilingual-v3.0",
                dims: 1024,
                label: "Cohere",
                sub: "1024 dims · Multilingual",
                icon: "ti-vector",
              },
              {
                key: "ollama",
                model: "embeddinggemma",
                dims: 768,
                label: "Ollama EmbeddingGemma",
                sub: "768 dims · Local",
                icon: "ti-server",
              },
            ].map((opt) => {
              const isActive =
                c?.embed_model === opt.model && c?.embed_dimensions === opt.dims;
              return (
                <div
                  key={opt.key}
                  className={cn(
                    "rounded-lg ring-1 p-4 flex items-center justify-between",
                    isActive
                      ? "ring-primary/40 bg-primary/5"
                      : "ring-foreground/10 bg-background",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "w-9 h-9 rounded-lg flex items-center justify-center",
                        isActive ? "bg-primary/10" : "bg-muted",
                      )}
                    >
                      <i
                        className={cn(
                          "ti text-base",
                          opt.icon,
                          isActive ? "text-primary" : "text-muted-foreground",
                        )}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{opt.label}</p>
                      <p className="text-[11px] text-muted-foreground">{opt.sub}</p>
                    </div>
                  </div>
                  <Button
                    variant={isActive ? "default" : "outline"}
                    size="sm"
                    disabled={isActive || switchMutation.isPending}
                    onClick={() =>
                      setConfirmTarget({ provider: opt.key, model: opt.model, dimensions: opt.dims })
                    }
                  >
                    {isActive ? (
                      "Active"
                    ) : switchMutation.isPending ? (
                      <i className="ti ti-loader-2 animate-spin text-sm" />
                    ) : (
                      "Switch"
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
          {switchResult && (
            <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
              {switchResult}
            </p>
          )}
        </div>
      </div>

      {/* Confirmation dialog */}
      {confirmTarget && (
        <ConfirmDialog
          title="Switch embedding provider"
          description={`This will re-embed all ${c?.embed_dimensions === 1024 && confirmTarget.dimensions === 768 ? "chunks (1024 → 768 dims)" : "chunks (768 → 1024 dims)"} using ${confirmTarget.provider}. This may take a few minutes.`}
          confirmLabel="Switch"
          onConfirm={() => {
            switchMutation.mutate(confirmTarget);
            setConfirmTarget(null);
          }}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
}

function ConfirmDialog({
  title,
  description,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.showModal();
    confirmButtonRef.current?.focus();
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") onCancel();
  }, [onCancel]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={onCancel}
      onKeyDown={handleKeyDown}
      className="backdrop:bg-black/50 bg-transparent rounded-xl shadow-2xl border border-border p-0 max-w-md w-full backdrop-blur-sm"
    >
      <form method="dialog" className="rounded-xl bg-card p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-warning/10 flex items-center justify-center shrink-0">
            <i className="ti ti-alert-triangle text-warning text-lg" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{description}</p>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-6">
          <Button variant="ghost" size="sm" type="button" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" size="sm" ref={confirmButtonRef} type="submit" onClick={(e) => { e.preventDefault(); onConfirm(); }}>
            {confirmLabel}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
