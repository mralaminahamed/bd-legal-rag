import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, BookOpen, MessageSquare, Settings } from "lucide-react";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "./ThemeToggle";
import { ConnectionBadge } from "./ConnectionBadge";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/acts", label: "Acts", icon: BookOpen, end: false },
  { to: "/playground", label: "Playground", icon: MessageSquare, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="flex w-56 flex-col border-r border-border bg-card">
        <div className="flex h-14 items-center border-b border-border px-4">
          <Logo />
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-3 flex items-center justify-between">
          <ConnectionBadge />
          <ThemeToggle />
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
