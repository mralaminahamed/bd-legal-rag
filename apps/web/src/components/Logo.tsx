// BD Legal RAG brand mark. Author: Al Amin Ahamed.
import { useId } from "react";

export function Logo({ size = 28 }: { size?: number }) {
  const uid = useId().replace(/:/g, "");
  const bgId = `logo-bg-${uid}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="BD Legal RAG"
      className="shrink-0"
    >
      <defs>
        <linearGradient id={bgId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1e3a6e" />
          <stop offset="100%" stopColor="#111827" />
        </linearGradient>
      </defs>

      {/* Background */}
      <rect width="32" height="32" rx="8" fill={`url(#${bgId})`} />

      {/* Scales beam */}
      <line x1="5" y1="11" x2="27" y2="11" stroke="rgba(255,255,255,0.9)" strokeWidth="1.5" strokeLinecap="round" />

      {/* Pivot — indigo accent dot at fulcrum */}
      <circle cx="16" cy="11" r="2.5" fill="#6366f1" />
      <circle cx="16" cy="11" r="1.2" fill="white" fillOpacity="0.7" />

      {/* Center post */}
      <line x1="16" y1="13" x2="16" y2="25" stroke="rgba(255,255,255,0.85)" strokeWidth="1.4" strokeLinecap="round" />

      {/* Base */}
      <line x1="11" y1="25" x2="21" y2="25" stroke="rgba(255,255,255,0.85)" strokeWidth="1.5" strokeLinecap="round" />

      {/* Left pan chain */}
      <line x1="5" y1="11" x2="4" y2="18.5" stroke="rgba(255,255,255,0.6)" strokeWidth="1.2" strokeLinecap="round" />
      {/* Left pan */}
      <path d="M1.5 18.5 Q4 22 6.5 18.5" stroke="rgba(255,255,255,0.9)" strokeWidth="1.4" fill="none" strokeLinecap="round" />

      {/* Right pan chain */}
      <line x1="27" y1="11" x2="28" y2="18.5" stroke="rgba(255,255,255,0.6)" strokeWidth="1.2" strokeLinecap="round" />
      {/* Right pan */}
      <path d="M25.5 18.5 Q28 22 30.5 18.5" stroke="rgba(255,255,255,0.9)" strokeWidth="1.4" fill="none" strokeLinecap="round" />
    </svg>
  );
}
