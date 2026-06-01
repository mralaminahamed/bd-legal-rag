import { cn } from "@/lib/utils";

interface LogoProps {
  collapsed?: boolean;
  className?: string;
}

export function Logo({ collapsed, className }: LogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      {/* Scales of Justice icon */}
      <svg
        width="32"
        height="32"
        viewBox="0 0 512 512"
        fill="none"
        className="shrink-0"
      >
        <rect width="512" height="512" rx="112" fill="#1d4ed8" />
        {/* Scale beam */}
        <line x1="160" y1="180" x2="352" y2="180" stroke="white" strokeWidth="20" strokeLinecap="round" />
        {/* Center post */}
        <line x1="256" y1="180" x2="256" y2="360" stroke="white" strokeWidth="20" strokeLinecap="round" />
        {/* Base */}
        <line x1="196" y1="360" x2="316" y2="360" stroke="white" strokeWidth="20" strokeLinecap="round" />
        {/* Left pan chain */}
        <line x1="160" y1="180" x2="140" y2="280" stroke="white" strokeWidth="14" strokeLinecap="round" />
        {/* Left pan */}
        <path d="M108 280 Q140 310 172 280" stroke="white" strokeWidth="14" fill="none" strokeLinecap="round" />
        {/* Right pan chain */}
        <line x1="352" y1="180" x2="372" y2="280" stroke="white" strokeWidth="14" strokeLinecap="round" />
        {/* Right pan */}
        <path d="M340 280 Q372 310 404 280" stroke="white" strokeWidth="14" fill="none" strokeLinecap="round" />
      </svg>

      {!collapsed && (
        <div className="min-w-0">
          <div className="text-sm font-bold text-[#E0EAF8] tracking-tight leading-tight">
            BD Legal
          </div>
          <div className="text-[9px] font-bold text-accent-text tracking-[1.5px] uppercase mt-px">
            RAG
          </div>
        </div>
      )}
    </div>
  );
}
