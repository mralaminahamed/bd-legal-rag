import { useTheme } from "next-themes";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className="text-[#4B6284] hover:text-[#8EB0D4] transition-colors p-1"
    >
      {theme === "dark" ? (
        <i className="ti ti-sun text-base" />
      ) : (
        <i className="ti ti-moon text-base" />
      )}
    </button>
  );
}
