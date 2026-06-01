import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm",
        "focus:outline-none focus:ring-2 focus:ring-primary",
        "placeholder:text-muted-foreground disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
