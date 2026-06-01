import { type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "secondary" | "success" | "warning" | "destructive";

const variantClasses: Record<BadgeVariant, string> = {
  default:
    "bg-accent/10 text-accent border border-accent/20",
  secondary:
    "bg-page text-text-3 border border-border",
  success:
    "bg-score-green-bg text-score-green border border-score-green-border",
  warning:
    "bg-score-amber-bg text-score-amber border border-score-amber-border",
  destructive:
    "bg-score-red-bg text-score-red border border-score-red-border",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
