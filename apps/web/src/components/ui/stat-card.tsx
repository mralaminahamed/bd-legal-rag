import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon?: string;
  iconClass?: string;
}

export function StatCard({
  title,
  value,
  sub,
  icon = "ti-chart-bar",
  iconClass = "text-accent",
}: StatCardProps) {
  return (
    <div className="bg-surface border border-border rounded-[10px] p-4">
      <div className="flex items-start justify-between mb-2">
        <span className="text-[11px] font-semibold text-text-3 uppercase tracking-wide leading-tight">
          {title}
        </span>
        <i className={cn(`ti ${icon} text-base`, iconClass)} />
      </div>
      <p className="text-2xl font-bold text-text-1 leading-tight tabular-nums">{value}</p>
      {sub && <p className="text-[11px] text-text-4 mt-1">{sub}</p>}
    </div>
  );
}
