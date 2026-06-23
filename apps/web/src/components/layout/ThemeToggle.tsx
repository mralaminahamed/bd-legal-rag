import { useState, useRef, useEffect } from "react";
import { useTheme } from "@/lib/themeContext";
import { THEMES, type ThemeId } from "@/lib/themes";
import { cn } from "@/lib/utils";

const GROUPS = {
  light: ["default", "rose", "emerald", "violet", "ocean", "amber"] as ThemeId[],
  dark: ["midnight", "nord", "catppuccin", "dracula", "tokyo-night", "gruvbox", "solarized", "everforest"] as ThemeId[],
};

function ThemeSwatch({ id, isActive }: { id: ThemeId; isActive: boolean }) {
  const t = THEMES[id];
  const c = t.colors;
  return (
    <div
      className={cn(
        "w-full aspect-[4/3] rounded-lg ring-1 overflow-hidden transition-all duration-150",
        isActive ? "ring-primary/60 shadow-sm" : "ring-foreground/10",
      )}
    >
      <div className="flex" style={{ height: "40%" }}>
        <div className="w-1/3 h-full" style={{ background: c["--nav"] }} />
        <div className="flex-1 h-full" style={{ background: c["--background"] }} />
      </div>
      <div className="flex" style={{ height: "60%" }}>
        <div className="w-1/3 h-full p-0.5 space-y-0.5" style={{ background: c["--nav"] }}>
          <div className="w-full h-1 rounded-sm" style={{ background: `${c["--primary"]}66` }} />
          <div className="w-full h-1 rounded-sm bg-white/10" />
        </div>
        <div className="flex-1 p-0.5 space-y-0.5" style={{ background: c["--background"] }}>
          <div className="h-1 w-6 rounded-sm" style={{ background: c["--muted"] }} />
          <div className="h-2 w-full rounded-sm" style={{ background: c["--card"] }} />
          <div className="h-2 w-3/4 rounded-sm" style={{ background: c["--card"] }} />
        </div>
      </div>
    </div>
  );
}

export function ThemeToggle({ inNav = false }: { inNav?: boolean }) {
  const { themeId } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("mousedown", handleClick);
      document.addEventListener("keydown", handleKey);
    }
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  if (inNav) {
    return (
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          aria-label="Change theme"
          aria-expanded={open}
          aria-haspopup="true"
          title={THEMES[themeId].label}
          className="text-nav-text hover:text-nav-text-active focus-visible:text-nav-text-active transition-colors p-1"
        >
          <i className="ti ti-palette text-base" />
        </button>
        {open && (
          <Dropdown onClose={() => setOpen(false)} />
        )}
      </div>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        aria-label="Change theme"
        aria-expanded={open}
        aria-haspopup="true"
        title={THEMES[themeId].label}
        className="inline-flex items-center gap-1.5 size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      >
        <i className="ti ti-palette text-sm" />
      </button>
      {open && (
        <Dropdown onClose={() => setOpen(false)} />
      )}
    </div>
  );
}

function Dropdown({ onClose }: { onClose: () => void }) {
  const { themeId, setThemeId } = useTheme();

  function select(id: ThemeId) {
    setThemeId(id);
    onClose();
  }

  return (
    <div className="absolute right-0 top-full mt-2 max-lg:right-0 max-lg:w-[calc(100dvw-32px)] lg:w-72 rounded-xl bg-card ring-1 ring-border shadow-xl z-50 p-3 space-y-2.5 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">Theme</span>
        <span className="text-[10px] text-muted-foreground">{THEMES[themeId].label}</span>
      </div>

      {/* Light */}
      <div>
        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">Light</p>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-1.5">
          {GROUPS.light.map((id) => (
            <button
              key={id}
              onClick={() => select(id)}
              className={cn(
                "rounded-lg p-1 transition-all duration-150 text-left",
                themeId === id
                  ? "bg-primary/10 ring-1 ring-primary/40"
                  : "hover:bg-muted/60 ring-1 ring-foreground/8",
              )}
            >
              <ThemeSwatch id={id} isActive={themeId === id} />
              <p className="text-[10px] font-medium text-foreground mt-1 truncate">{THEMES[id].label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Dark */}
      <div>
        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">Dark</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-1.5">
          {GROUPS.dark.map((id) => (
            <button
              key={id}
              onClick={() => select(id)}
              className={cn(
                "rounded-lg p-1 transition-all duration-150 text-left",
                themeId === id
                  ? "bg-primary/10 ring-1 ring-primary/40"
                  : "hover:bg-muted/60 ring-1 ring-foreground/8",
              )}
            >
              <ThemeSwatch id={id} isActive={themeId === id} />
              <p className="text-[9px] font-medium text-foreground mt-1 truncate">{THEMES[id].label}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
