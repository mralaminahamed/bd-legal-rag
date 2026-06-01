import { forwardRef, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex h-8 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm text-foreground",
        "focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring",
        "disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
