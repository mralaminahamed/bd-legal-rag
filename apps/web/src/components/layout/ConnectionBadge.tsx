import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/admin";
import { cn } from "@/lib/utils";

export function ConnectionBadge() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const ok = !isError && data?.status === "ok";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        ok
          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
          : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", ok ? "bg-green-500" : "bg-red-500")} />
      {ok ? "online" : "offline"}
    </span>
  );
}
