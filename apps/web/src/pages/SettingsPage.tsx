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
import { Save, Trash2 } from "lucide-react";

const PROVIDERS = ["anthropic", "openai", "ollama"] as const;

const MODELS: Record<string, string[]> = {
  anthropic: [
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-haiku-4-5-20251001",
  ],
  openai: ["gpt-4o-mini", "gpt-4o"],
  ollama: ["llama3.2", "mistral"],
};

export function SettingsPage() {
  const qc = useQueryClient();
  const [tokenInput, setTokenInput] = useState(getAdminToken() ?? "");
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-6");

  const overrideQ = useQuery({
    queryKey: ["admin", "llm"],
    queryFn: getLLMOverride,
    retry: false,
  });

  const healthQ = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: false,
    refetchInterval: 30_000,
  });

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
      toast.success("Override cleared — reverted to env defaults");
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

  return (
    <div className="flex flex-col">
      <PageHeader
        title="Settings"
        description="Admin token and LLM provider configuration"
      />

      <div className="p-6 space-y-6 max-w-2xl">
        {/* Admin token */}
        <Card>
          <CardHeader>
            <CardTitle>Admin bearer token</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Stored in localStorage. Required for admin API access.
            </p>
            <div className="flex gap-2">
              <Input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Enter admin bearer token"
                className="flex-1"
              />
              <Button onClick={saveToken}>
                <Save className="h-4 w-4" />
                Save
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Health probe */}
        <Card>
          <CardHeader>
            <CardTitle>Service health</CardTitle>
          </CardHeader>
          <CardContent>
            {healthQ.data ? (
              <div className="flex gap-4 text-sm">
                <div>
                  Status:{" "}
                  <Badge
                    variant={
                      healthQ.data.status === "ok" ? "success" : "destructive"
                    }
                  >
                    {healthQ.data.status}
                  </Badge>
                </div>
                <div>
                  DB:{" "}
                  <Badge
                    variant={
                      healthQ.data.database === "ok" ? "success" : "destructive"
                    }
                  >
                    {healthQ.data.database}
                  </Badge>
                </div>
                <div>
                  Redis:{" "}
                  <Badge
                    variant={
                      healthQ.data.redis === "ok" ? "success" : "destructive"
                    }
                  >
                    {healthQ.data.redis}
                  </Badge>
                </div>
              </div>
            ) : (
              <Skeleton className="h-5 w-64" />
            )}
          </CardContent>
        </Card>

        {/* LLM override */}
        <Card>
          <CardHeader>
            <CardTitle>LLM provider override</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {overrideQ.data ? (
              <div className="text-sm">
                Active:{" "}
                <code className="bg-muted px-1 rounded text-xs">
                  {overrideQ.data.provider}
                </code>{" "}
                /{" "}
                <code className="bg-muted px-1 rounded text-xs">
                  {overrideQ.data.model}
                </code>{" "}
                <Badge
                  variant={
                    overrideQ.data.source === "override" ? "default" : "secondary"
                  }
                >
                  {overrideQ.data.source}
                </Badge>
              </div>
            ) : (
              <Skeleton className="h-5 w-48" />
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
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
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="model">Model</Label>
                <Select
                  id="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {(MODELS[provider] ?? []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={() => setOverride.mutate()}
                disabled={setOverride.isPending}
              >
                <Save className="h-4 w-4" />
                Set override
              </Button>
              <Button
                variant="outline"
                onClick={() => clearOverride.mutate()}
                disabled={clearOverride.isPending}
              >
                <Trash2 className="h-4 w-4" />
                Clear override
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
