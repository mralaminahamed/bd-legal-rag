// App layout — collapsible sidebar + max-width content. Author: Al Amin Ahamed.
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import { useLang } from "@/lib/langContext";
import { ConnectionBadge } from "./ConnectionBadge";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/", label: "Dashboard", icon: "ti-layout-dashboard", end: true },
  { to: "/acts", label: "Acts Registry", icon: "ti-books", end: false },
  {
    to: "/playground",
    label: "Playground",
    icon: "ti-message-chatbot",
    end: false,
  },
];

function NavItem({
  to,
  label,
  icon,
  end,
  collapsed,
}: {
  to: string;
  label: string;
  icon: string;
  end: boolean;
  collapsed: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      title={label}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all",
          collapsed && "justify-center px-0 w-9 mx-auto",
          isActive
            ? "bg-white/10 text-white"
            : "text-[#5c7a9e] hover:bg-white/6 hover:text-[#a8c4e0]",
        )
      }
    >
      <i className={`ti ${icon} text-[15px] shrink-0`} />
      {!collapsed && (
        <span className="flex-1 truncate leading-none">{label}</span>
      )}
    </NavLink>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebar-collapsed") === "true",
  );
  const { uiLang, setUiLang } = useLang();
  const location = useLocation();
  const isPlayground = location.pathname.startsWith("/playground");

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  }

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col shrink-0 transition-[width] duration-200 ease-in-out overflow-x-hidden",
          collapsed ? "w-[60px]" : "w-[220px]",
        )}
        style={{ backgroundColor: "var(--nav)" }}
      >
        {/* Logo row */}
        <div
          className={cn(
            "flex items-center shrink-0 h-14",
            collapsed ? "justify-center px-0" : "px-4 gap-2.5",
          )}
        >
          <div className="shrink-0">
            <Logo size={26} />
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-bold text-white/90 tracking-tight leading-tight">
                BD Legal
              </div>
              <div className="text-[10px] font-semibold text-white/30 tracking-[0.12em] uppercase leading-tight mt-px">
                RAG
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-3 h-px bg-white/6 shrink-0" />

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5 overflow-y-auto overflow-x-hidden">
          {NAV.map((item) => (
            <NavItem
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
              end={item.end}
              collapsed={collapsed}
            />
          ))}
        </nav>

        {/* Bottom — collapse toggle */}
        <div className="mx-3 h-px bg-white/6 shrink-0" />
        <div
          className={cn(
            "flex shrink-0 h-11 items-center",
            collapsed ? "justify-center" : "px-2",
          )}
        >
          <button
            onClick={toggleCollapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex items-center gap-2 rounded-lg px-2.5 py-2 text-[12px] font-medium text-[#5c7a9e]",
              "hover:bg-white/6 hover:text-[#a8c4e0] transition-all w-full",
              collapsed && "justify-center px-0 w-9 mx-auto",
            )}
          >
            <i
              className={cn(
                "ti text-[15px] shrink-0",
                collapsed
                  ? "ti-layout-sidebar-left-expand"
                  : "ti-layout-sidebar-left-collapse",
              )}
            />
            {!collapsed && <span className="flex-1 truncate">Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 min-w-0 flex-col overflow-y-auto max-h-screen">
        {/* Top bar */}
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-6 backdrop-blur-sm shrink-0">
          <div className="flex-1" />

          {/* Language toggle — only on playground routes */}
          {isPlayground && (
            <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
              {(["en", "bn"] as const).map((lang) => (
                <button
                  key={lang}
                  onClick={() => setUiLang(lang)}
                  title={
                    lang === "en" ? "English response" : "Bengali response"
                  }
                  className={cn(
                    "px-3 py-1 rounded-md text-xs font-semibold transition-colors",
                    uiLang === lang
                      ? "bg-background text-foreground shadow-sm ring-1 ring-foreground/10"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {lang === "en" ? "English" : "বাংলা"}
                </button>
              ))}
            </div>
          )}

          <ConnectionBadge />
          <ThemeToggle />
        </header>

        {/* Page content */}
        <main className="mx-auto w-full max-w-[1100px] p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
