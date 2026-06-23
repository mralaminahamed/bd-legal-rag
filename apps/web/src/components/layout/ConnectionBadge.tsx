import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/admin";
import { cn } from "@/lib/utils";

export function ConnectionBadge({ collapsed, compact }: { collapsed?: boolean; compact?: boolean }) {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const ok = !isError && data?.status === "ok";

  if (compact) {
    return (
      <span
        title={ok ? "API online" : "API offline"}
        className={cn("w-2 h-2 rounded-full shrink-0", ok ? "bg-success" : "bg-destructive")}
      />
    );
  }

  if (collapsed) {
    return (
      <span
        title={ok ? "API online" : "API offline"}
        className={cn("w-2 h-2 rounded-full shrink-0", ok ? "bg-success" : "bg-destructive")}
      />
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium border",
        ok
          ? "bg-success/10 text-success border-success/20"
          : "bg-destructive/10 text-destructive border-destructive/20",
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", ok ? "bg-success" : "bg-destructive")} />
      {ok ? "online" : "offline"}
    </span>
  );
}
