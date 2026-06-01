import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getLLMOverride,
  setLLMOverride,
  clearLLMOverride,
  getHealth,
} from "@/api/admin";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getAdminToken, setAdminToken, clearAdminToken } from "@/lib/config";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const PROVIDERS = ["anthropic", "openai", "ollama"] as const;
const MODELS: Record<string, string[]> = {
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
  openai: ["gpt-4o-mini", "gpt-4o"],
  ollama: ["llama3.2", "mistral", "gemma4:e2b"],
};

function HealthDot({ ok }: { ok: boolean }) {
  return (
    <span className={cn("w-2 h-2 rounded-full shrink-0", ok ? "bg-success" : "bg-destructive")} />
  );
}

export function SettingsPage() {
  const qc = useQueryClient();
  const [tokenInput, setTokenInput] = useState(getAdminToken() ?? "");
  const [showToken, setShowToken] = useState(false);
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-6");

  const overrideQ = useQuery({ queryKey: ["admin", "llm"], queryFn: getLLMOverride, retry: false });
  const healthQ = useQuery({ queryKey: ["health"], queryFn: getHealth, retry: false, refetchInterval: 30_000 });

  const setOverride = useMutation({
    mutationFn: () => setLLMOverride({ provider, model }),
    onSuccess: (data) => {
      toast.success(`Override set: ${data.provider} / ${data.model}`);
      void qc.invalidateQueries({ queryKey: ["admin", "llm"] });
    },
    onError: () => toast.error("Failed to set override — check bearer token"),
  });

  const clearOverride = useMutation({
    mutationFn: clearLLMOverride,
    onSuccess: () => {
      toast.success("Override cleared");
      void qc.invalidateQueries({ queryKey: ["admin", "llm"] });
    },
    onError: () => toast.error("Failed to clear override"),
  });

  function saveToken() {
    if (tokenInput.trim()) {
      setAdminToken(tokenInput.trim());
      toast.success("Token saved");
      void qc.invalidateQueries();
    } else {
      clearAdminToken();
      toast.info("Token cleared");
    }
  }

  const h = healthQ.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Settings"
        description="Admin token and LLM provider configuration."
      />

      <div className="max-w-2xl space-y-4">
        {/* Admin token */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <i className="ti ti-key text-sm text-primary" />
              Admin bearer token
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Stored in localStorage. Required for all admin API endpoints.
            </p>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={showToken ? "text" : "password"}
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="Enter admin bearer token"
                  className="pr-9"
                />
                <button
                  type="button"
                  onClick={() => setShowToken((s) => !s)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <i className={`ti ${showToken ? "ti-eye-off" : "ti-eye"} text-sm`} />
                </button>
              </div>
              <Button onClick={saveToken}>
                <i className="ti ti-device-floppy text-sm" /> Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Service health */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <i className="ti ti-activity text-sm text-primary" />
              Service health
            </CardTitle>
          </CardHeader>
          <CardContent>
            {h ? (
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "API", status: h.status },
                  { label: "Database", status: h.database },
                  { label: "Redis", status: h.redis },
                ].map(({ label, status }) => (
                  <div key={label} className="flex items-center gap-2.5 rounded-lg bg-muted/50 px-3 py-2.5">
                    <HealthDot ok={status === "ok"} />
                    <div>
                      <div className="text-[11px] font-semibold text-muted-foreground">{label}</div>
                      <div className={cn("text-xs font-bold", status === "ok" ? "text-success" : "text-destructive")}>
                        {status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Skeleton className="h-16 w-full" />
            )}
          </CardContent>
        </Card>

        {/* LLM override */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <i className="ti ti-cpu text-sm text-primary" />
              LLM provider override
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {overrideQ.data ? (
              <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2">
                <span className="text-xs text-muted-foreground">Active:</span>
                <code className="text-xs font-mono bg-background px-1.5 py-0.5 rounded border border-border">
                  {overrideQ.data.provider}
                </code>
                <span className="text-muted-foreground text-xs">/</span>
                <code className="text-xs font-mono bg-background px-1.5 py-0.5 rounded border border-border">
                  {overrideQ.data.model}
                </code>
                <Badge variant={overrideQ.data.source === "override" ? "default" : "secondary"}>
                  {overrideQ.data.source}
                </Badge>
              </div>
            ) : (
              <Skeleton className="h-10 w-full" />
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="provider">Provider</Label>
                <Select
                  id="provider"
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value);
                    setModel(MODELS[e.target.value]?.[0] ?? "");
                  }}
                >
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="model">Model</Label>
                <Select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
                  {(MODELS[provider] ?? []).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex gap-2">
              <Button onClick={() => setOverride.mutate()} disabled={setOverride.isPending}>
                <i className="ti ti-device-floppy text-sm" /> Set override
              </Button>
              <Button variant="outline" onClick={() => clearOverride.mutate()} disabled={clearOverride.isPending}>
                <i className="ti ti-trash text-sm" /> Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
