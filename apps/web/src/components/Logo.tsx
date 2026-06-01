import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
}

export function Logo({ className }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2 font-semibold", className)}>
      <span className="text-blue-600 dark:text-blue-400 text-xl">⚖</span>
      <span className="text-sm tracking-tight">BD Legal RAG</span>
    </div>
  );
}
