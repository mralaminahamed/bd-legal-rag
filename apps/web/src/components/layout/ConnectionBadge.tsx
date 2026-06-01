import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/admin";
import { cn } from "@/lib/utils";

interface ConnectionBadgeProps {
  collapsed?: boolean;
}

export function ConnectionBadge({ collapsed }: ConnectionBadgeProps) {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const ok = !isError && data?.status === "ok";

  if (collapsed) {
    return (
      <span
        title={ok ? "API online" : "API offline"}
        className={cn(
          "w-2 h-2 rounded-full",
          ok ? "bg-score-green" : "bg-score-red"
        )}
      />
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium",
        ok
          ? "bg-score-green-bg text-score-green border border-score-green-border"
          : "bg-score-red-bg text-score-red border border-score-red-border"
      )}
    >
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          ok ? "bg-score-green" : "bg-score-red"
        )}
      />
      {ok ? "online" : "offline"}
    </span>
  );
}
