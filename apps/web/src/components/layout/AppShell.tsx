// App layout: collapsible navy sidebar + max-width content. Author: Al Amin Ahamed.
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import { ConnectionBadge } from "./ConnectionBadge";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/", label: "Dashboard", icon: "ti-layout-dashboard", end: true },
  { to: "/acts", label: "Acts Registry", icon: "ti-books", end: false },
  { to: "/playground", label: "Playground", icon: "ti-message-chatbot", end: false },
  { to: "/settings", label: "Settings", icon: "ti-settings", end: false },
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
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center py-2 text-[13px] font-medium rounded-r-lg",
          "border-l-2 -ml-2 transition-colors cursor-pointer select-none",
          collapsed ? "justify-center px-3" : "gap-2.5 px-4",
          isActive
            ? "bg-nav-active-bg text-nav-text-active border-l-primary"
            : "text-nav-text border-l-transparent hover:bg-white/5 hover:text-[#8eb0d4]",
        )
      }
    >
      <i className={`ti ${icon} text-base shrink-0`} />
      {!collapsed && <span className="flex-1 truncate">{label}</span>}
    </NavLink>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sidebar-collapsed") === "true",
  );

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  }

  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col shrink-0 transition-[width] duration-200 ease-in-out overflow-x-hidden",
          collapsed ? "w-14" : "w-54",
        )}
        style={{ backgroundColor: "var(--nav)" }}
      >
        {/* Logo */}
        <div
          className={cn(
            "py-4 border-b flex items-center gap-2.5 shrink-0",
            collapsed ? "justify-center px-0" : "px-4",
          )}
          style={{ borderColor: "var(--nav-border)" }}
        >
          <Logo size={28} />
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-bold text-[#e0eaf8] tracking-tight leading-none">
                  BD Legal
                </div>
                <div className="text-[9px] font-bold text-primary tracking-[1.5px] uppercase mt-1">
                  RAG
                </div>
              </div>
              <button
                onClick={toggleCollapsed}
                title="Collapse sidebar"
                className="shrink-0 text-nav-text hover:text-[#8eb0d4] transition-colors"
              >
                <i className="ti ti-chevrons-left text-sm" />
              </button>
            </>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 flex flex-col gap-px overflow-y-auto overflow-x-hidden">
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

          <div className="mt-auto pt-2">
            <button
              onClick={toggleCollapsed}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={cn(
                "flex items-center w-full py-2 text-[13px] font-medium rounded-r-lg",
                "border-l-2 border-l-transparent -ml-2 transition-colors",
                "text-nav-text hover:bg-white/5 hover:text-[#8eb0d4]",
                collapsed ? "justify-center px-3" : "gap-2.5 px-4",
              )}
            >
              <i
                className={cn(
                  "ti text-sm shrink-0",
                  collapsed ? "ti-chevrons-right" : "ti-chevrons-left",
                )}
              />
              {!collapsed && <span className="flex-1 text-xs">Collapse</span>}
            </button>
          </div>
        </nav>
      </aside>

      {/* Main */}
      <div className="flex flex-1 min-w-0 flex-col overflow-y-auto max-h-screen">
        {/* Sticky top bar */}
        <header className="sticky top-0 z-10 flex h-12 items-center gap-3 border-b border-border bg-card/80 px-6 backdrop-blur-sm shrink-0">
          <div className="flex-1" />
          <ConnectionBadge />
          <ThemeToggle />
        </header>

        {/* Page content — max width constraint */}
        <main className="mx-auto w-full max-w-[1100px] p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
