import { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { ReactNode } from "react";
import { type ThemeId, THEMES, DEFAULT_THEME } from "./themes";

interface ThemeContextValue {
  themeId: ThemeId;
  setThemeId: (id: ThemeId) => void;
}

const STORAGE_KEY = "bd-legal-rag-theme";

const ThemeContext = createContext<ThemeContextValue>({
  themeId: DEFAULT_THEME,
  setThemeId: () => undefined,
});

function applyTheme(id: ThemeId) {
  const el = document.documentElement;
  const theme = THEMES[id];
  const isDark = theme.dark;

  // Remove all theme-* classes
  el.className = el.className.replace(/theme-\S+/g, "").trim();
  // Remove .dark
  el.classList.remove("dark");

  // Apply theme class
  if (id !== DEFAULT_THEME) {
    el.classList.add(`theme-${id}`);
  }
  // Apply dark if the theme is dark
  if (isDark) {
    el.classList.add("dark");
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeId, setThemeIdState] = useState<ThemeId>(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    if (stored && THEMES[stored]) return stored;
    // Respect system preference
    if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
      return "midnight";
    }
    return DEFAULT_THEME;
  });

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  const setThemeId = useCallback((id: ThemeId) => {
    localStorage.setItem(STORAGE_KEY, id);
    setThemeIdState(id);
  }, []);

  return (
    <ThemeContext.Provider value={{ themeId, setThemeId }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
