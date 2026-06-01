import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "./ThemeToggle";
import { ConnectionBadge } from "./ConnectionBadge";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: "ti-layout-dashboard", end: true },
  { to: "/acts", label: "Acts Registry", icon: "ti-books", end: false },
  { to: "/playground", label: "Playground", icon: "ti-message-question", end: false },
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
            ? "bg-accent/[0.14] text-accent-text border-l-accent"
            : "text-[#4B6284] border-l-transparent hover:bg-white/5 hover:text-[#8EB0D4]"
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
    () => localStorage.getItem("sidebar-collapsed") === "true"
  );

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  };

  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside
        className={cn(
          "bg-nav flex flex-col shrink-0 transition-[width] duration-200 ease-in-out overflow-x-hidden",
          collapsed ? "w-14" : "w-56"
        )}
      >
        {/* Logo */}
        <div
          className={cn(
            "py-4 border-b border-nav-border flex items-center gap-2.5 shrink-0",
            collapsed ? "justify-center px-0" : "px-4"
          )}
        >
          <Logo collapsed={collapsed} />
          {!collapsed && (
            <button
              onClick={toggleCollapsed}
              title="Collapse sidebar"
              className="shrink-0 ml-auto text-[#4B6284] hover:text-[#8EB0D4] transition-colors"
            >
              <i className="ti ti-chevrons-left text-sm" />
            </button>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2.5 flex flex-col gap-px overflow-y-auto overflow-x-hidden">
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

          {/* Collapse toggle at bottom */}
          <div className="mt-auto pt-2">
            <button
              onClick={toggleCollapsed}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={cn(
                "flex items-center w-full py-2 text-[13px] font-medium rounded-r-lg",
                "border-l-2 border-l-transparent -ml-2 transition-colors",
                "text-[#4B6284] hover:bg-white/5 hover:text-[#8EB0D4]",
                collapsed ? "justify-center px-3" : "gap-2.5 px-4"
              )}
            >
              <i
                className={cn(
                  "ti text-base shrink-0",
                  collapsed ? "ti-chevrons-right" : "ti-chevrons-left"
                )}
              />
              {!collapsed && <span className="flex-1">Collapse</span>}
            </button>
          </div>
        </nav>

        {/* Footer */}
        <div
          className={cn(
            "border-t border-nav-border shrink-0 flex items-center gap-2",
            collapsed ? "flex-col py-3 px-0 justify-center" : "px-3 py-2.5"
          )}
        >
          <ConnectionBadge collapsed={collapsed} />
          <ThemeToggle />
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col overflow-y-auto max-h-screen">
        <Outlet />
      </main>
    </div>
  );
}
