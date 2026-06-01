import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function ThemeToggle({ inNav = false }: { inNav?: boolean }) {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <span className="w-7 h-7" />;

  const isDark = resolvedTheme === "dark";

  if (inNav) {
    return (
      <button
        onClick={() => setTheme(isDark ? "light" : "dark")}
        aria-label="Toggle theme"
        className="text-nav-text hover:text-[#8eb0d4] transition-colors p-1"
      >
        <i className={`ti ${isDark ? "ti-sun" : "ti-moon"} text-base`} />
      </button>
    );
  }

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="inline-flex items-center justify-center size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
    >
      <i className={`ti ${isDark ? "ti-sun" : "ti-moon"} text-sm`} />
    </button>
  );
}
