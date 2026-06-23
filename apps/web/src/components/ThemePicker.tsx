import { useState } from "react";
import { useTheme } from "@/lib/themeContext";
import { THEMES, type ThemeId } from "@/lib/themes";
import { cn } from "@/lib/utils";

const GROUPS = {
  light: ["default", "rose", "emerald", "violet", "ocean", "amber"] as ThemeId[],
  dark: ["midnight", "nord", "catppuccin", "dracula", "tokyo-night", "gruvbox", "solarized", "everforest"] as ThemeId[],
};

/** Mini browser-chrome preview of a theme */
function ThemePreviewCard({
  id,
  isActive,
  onSelect,
  onHover,
  onLeave,
}: {
  id: ThemeId;
  isActive: boolean;
  onSelect: () => void;
  onHover: () => void;
  onLeave: () => void;
}) {
  const t = THEMES[id];
  const c = t.colors;

  return (
    <button
      onClick={onSelect}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      className={cn(
        "group relative rounded-xl ring-1 transition-all duration-200 text-left overflow-hidden",
        isActive
          ? "ring-primary/60 shadow-lg shadow-primary/10 scale-[1.02]"
          : "ring-foreground/10 hover:ring-foreground/20 hover:shadow-md hover:scale-[1.01]",
      )}
    >
      {/* Browser chrome */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1.5"
        style={{ background: c["--nav"] }}
      >
        <div className="flex gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
          <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
          <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
        </div>
        <div
          className="flex-1 mx-2 h-3.5 rounded-md text-center"
          style={{ background: `${c["--card"]}22` }}
        />
      </div>

      {/* Mini app preview */}
      <div style={{ background: c["--background"] }} className="p-2 space-y-1.5">
        {/* Mini sidebar + content */}
        <div className="flex gap-1.5" style={{ height: 52 }}>
          {/* Sidebar */}
          <div
            className="w-5 rounded-md shrink-0 flex flex-col gap-0.5 p-0.5"
            style={{ background: c["--nav"] }}
          >
            <div className="w-full h-1 rounded-sm" style={{ background: `${c["--primary"]}88` }} />
            <div className="w-full h-1 rounded-sm bg-white/10" />
            <div className="w-full h-1 rounded-sm bg-white/10" />
            <div className="w-full h-1 rounded-sm bg-white/10" />
          </div>
          {/* Content area */}
          <div className="flex-1 space-y-1">
            <div className="h-1.5 w-12 rounded-sm" style={{ background: c["--muted"] }} />
          <div className="flex gap-1">
            <div className="h-6 flex-1 rounded-md" style={{ background: c["--card"], boxShadow: `inset 0 0 0 1px ${c["--border"]}` }} />
            <div className="h-6 flex-1 rounded-md" style={{ background: c["--card"], boxShadow: `inset 0 0 0 1px ${c["--border"]}` }} />
          </div>
          <div className="h-1.5 w-16 rounded-sm" style={{ background: c["--muted"] }} />
          </div>
        </div>

        {/* Mini chat bubbles */}
        <div className="flex gap-1 items-end">
          <div className="w-8 h-3 rounded-md rounded-br-sm" style={{ background: c["--primary"] }} />
          <div className="w-12 h-4 rounded-md rounded-bl-sm ml-auto" style={{ background: c["--card"], boxShadow: `inset 0 0 0 1px ${c["--border"]}` }} />
        </div>

        {/* Mini input */}
        <div className="h-3 rounded-md" style={{ background: c["--card"], boxShadow: `inset 0 0 0 1px ${c["--border"]}` }} />
      </div>

      {/* Label */}
      <div className="flex items-center justify-between px-2.5 py-1.5" style={{ background: c["--card"] }}>
        <span className="text-[11px] font-semibold" style={{ color: c["--foreground"] }}>
          {t.label}
        </span>
        {isActive && (
          <span
            className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full"
            style={{ background: `${c["--primary"]}20`, color: c["--primary"] }}
          >
            Active
          </span>
        )}
      </div>

      {/* Active ring glow */}
      {isActive && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{
            boxShadow: `inset 0 0 0 2px ${c["--primary"]}30`,
          }}
        />
      )}
    </button>
  );
}

export function ThemePicker() {
  const { themeId, setThemeId } = useTheme();
  const [hovered, setHovered] = useState<ThemeId | null>(null);

  const previewId = hovered ?? themeId;
  const preview = THEMES[previewId].colors;

  return (
    <div className="space-y-5">
      {/* Live palette preview */}
      <div
        className="flex items-center gap-4 p-4 rounded-xl ring-1 ring-foreground/8 transition-all duration-300"
        style={{ background: preview["--card"] }}
      >
        <div className="flex gap-1.5">
          {[
            { color: preview["--background"], label: "BG" },
            { color: preview["--card"], label: "Card" },
            { color: preview["--primary"], label: "Primary" },
            { color: preview["--accent"] || preview["--secondary"], label: "Accent" },
            { color: preview["--nav"], label: "Nav" },
            { color: preview["--muted"], label: "Muted" },
          ].map((c) => (
            <div
              key={c.label}
              title={c.label}
              className="w-8 h-8 rounded-lg ring-1 ring-foreground/10 transition-all duration-200 hover:scale-110"
              style={{ background: c.color }}
            />
          ))}
        </div>
        <div className="ml-auto text-right">
          <p className="text-xs font-medium" style={{ color: preview["--foreground"] }}>
            {THEMES[previewId].label}
          </p>
          <p className="text-[10px]" style={{ color: preview["--muted-foreground"] }}>
            {THEMES[previewId].dark ? "Dark mode" : "Light mode"}
          </p>
        </div>
      </div>

      {/* Light themes */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <i className="ti ti-sun text-sm text-muted-foreground" />
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Light
          </p>
          <div className="flex-1 h-px bg-border/60" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2.5">
          {GROUPS.light.map((id) => (
            <ThemePreviewCard
              key={id}
              id={id}
              isActive={themeId === id}
              onSelect={() => setThemeId(id)}
              onHover={() => setHovered(id)}
              onLeave={() => setHovered(null)}
            />
          ))}
        </div>
      </div>

      {/* Dark themes */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <i className="ti ti-moon text-sm text-muted-foreground" />
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Dark
          </p>
          <div className="flex-1 h-px bg-border/60" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
          {GROUPS.dark.map((id) => (
            <ThemePreviewCard
              key={id}
              id={id}
              isActive={themeId === id}
              onSelect={() => setThemeId(id)}
              onHover={() => setHovered(id)}
              onLeave={() => setHovered(null)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
