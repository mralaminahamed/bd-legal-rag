// BD Legal RAG — Shapla (Bangladesh national water lily) brand mark.
// Author: Al Amin Ahamed.
import { useId } from "react";

export function Logo({ size = 28 }: { size?: number }) {
  const uid = useId().replace(/:/g, "");
  const bgId = `logo-bg-${uid}`;

  // Shapla petal path: teardrop pointing outward (-y), base near center at y=-2.5
  const petal = "M0,-2.5 C2.8,-4 2.8,-8 0,-11 C-2.8,-8 -2.8,-4 0,-2.5 Z";

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
          <stop offset="0%" stopColor="var(--nav, #1a2744)" />
          <stop offset="100%" stopColor="var(--nav, #1a2744)" stopOpacity="0.7" />
        </linearGradient>
      </defs>

      {/* Background */}
      <rect width="32" height="32" rx="8" fill={`url(#${bgId})`} />

      {/* Shapla — 5 petals at 72° intervals */}
      <g transform="translate(16,16)">
        <path d={petal} fill="rgba(255,255,255,0.92)" />
        <path d={petal} fill="rgba(255,255,255,0.82)" transform="rotate(72)" />
        <path d={petal} fill="rgba(255,255,255,0.88)" transform="rotate(144)" />
        <path d={petal} fill="rgba(255,255,255,0.82)" transform="rotate(216)" />
        <path d={petal} fill="rgba(255,255,255,0.88)" transform="rotate(288)" />
      </g>

      {/* Center — primary accent */}
      <circle cx="16" cy="16" r="3" fill="var(--primary, #6366f1)" />
      <circle cx="16" cy="16" r="1.4" fill="white" fillOpacity="0.85" />
    </svg>
  );
}
