// BD Legal RAG brand mark: scales of justice + knowledge graph. Author: Al Amin Ahamed.
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
          <stop offset="0%" stopColor="#233468" />
          <stop offset="100%" stopColor="#1a2744" />
        </linearGradient>
      </defs>

      {/* Badge background */}
      <rect width="32" height="32" rx="7.5" fill={`url(#${bgId})`} />

      {/* Scales beam */}
      <line x1="8" y1="11" x2="24" y2="11" stroke="white" strokeWidth="1.6" strokeLinecap="round" />
      {/* Center post */}
      <line x1="16" y1="11" x2="16" y2="25" stroke="white" strokeWidth="1.6" strokeLinecap="round" />
      {/* Base */}
      <line x1="12" y1="25" x2="20" y2="25" stroke="white" strokeWidth="1.6" strokeLinecap="round" />

      {/* Left pan */}
      <line x1="8" y1="11" x2="6.5" y2="18" stroke="rgba(255,255,255,0.75)" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M4 18 Q6.5 21.5 9 18" stroke="rgba(255,255,255,0.9)" strokeWidth="1.3" fill="none" strokeLinecap="round" />

      {/* Right pan */}
      <line x1="24" y1="11" x2="25.5" y2="18" stroke="rgba(255,255,255,0.75)" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M23 18 Q25.5 21.5 28 18" stroke="rgba(255,255,255,0.9)" strokeWidth="1.3" fill="none" strokeLinecap="round" />

      {/* RAG graph nodes — top right corner */}
      <circle cx="25" cy="5.5" r="2" fill="#818cf8" />
      <circle cx="29" cy="9.5" r="1.6" fill="#6366f1" />
      <line x1="25" y1="5.5" x2="29" y2="9.5" stroke="#818cf8" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}
