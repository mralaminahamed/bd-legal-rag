import { type ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-surface px-6 py-4 shrink-0 sticky top-0 z-10">
      <div>
        <h1 className="text-[15px] font-bold text-text-1">{title}</h1>
        {description && (
          <p className="mt-0.5 text-[12px] text-text-4">{description}</p>
        )}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  );
}
