// App layout — collapsible sidebar + max-width content. Author: Al Amin Ahamed.
import { useState, useRef, useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import { useLang } from "@/lib/langContext";
import { useIsMobile } from "@/lib/useIsMobile";
import { ConnectionBadge } from "./ConnectionBadge";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/", label: "Dashboard", icon: "ti-layout-dashboard", end: true },
  { to: "/acts", label: "Acts Registry", icon: "ti-books", end: false },
  { to: "/threads", label: "Conversations", icon: "ti-messages", end: false },
  {
    to: "/playground",
    label: "Playground",
    icon: "ti-message-chatbot",
    end: false,
  },
  { to: "/settings", label: "Settings", icon: "ti-settings", end: false },
];

function NavItem({
  to,
  label,
  icon,
  end,
  collapsed,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: string;
  end: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      title={label}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all",
          collapsed && "justify-center px-0 w-9 mx-auto",
          isActive
            ? "bg-nav-active-bg text-nav-text-active"
            : "text-nav-text hover:bg-nav-active-bg/50 hover:text-nav-text-active",
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
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);
  const isPlayground = location.pathname.startsWith("/playground");
  const isReader = location.pathname.includes("/read");

  useEffect(() => {
    if (!isMobile || !drawerOpen) return;
    const firstFocusable = sidebarRef.current?.querySelector<HTMLElement>(
      'a, button, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();
  }, [isMobile, drawerOpen]);

  useEffect(() => {
    if (!isMobile || drawerOpen) return;
    hamburgerRef.current?.focus();
  }, [isMobile, drawerOpen]);

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("sidebar-collapsed", String(next));
      return next;
    });
  }

  return (
    <div className="flex min-h-screen w-full bg-background">
      {/* Skip to content */}
      <a
        href="#main-content"
        onClick={() => setDrawerOpen(false)}
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>
      {/* Sidebar — desktop: fixed sidebar, mobile: overlay drawer */}
      <aside
        ref={sidebarRef}
        className={cn(
          "flex flex-col shrink-0 overflow-x-hidden",
          isMobile
            ? "fixed inset-y-0 left-0 z-40 w-[260px] max-w-[85vw] transition-transform duration-200 ease-in-out"
            : "transition-[width] duration-200 ease-in-out",
          collapsed && !isMobile ? "w-[60px]" : isMobile ? "" : "w-[220px]",
          isMobile && !drawerOpen && "-translate-x-full",
        )}
        style={{ backgroundColor: "var(--nav)" }}
        aria-modal={isMobile && drawerOpen ? "true" : undefined}
        role={isMobile && drawerOpen ? "dialog" : undefined}
        aria-label={isMobile && drawerOpen ? "Navigation menu" : undefined}
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
              <div className="text-[13px] font-bold text-nav-text-active tracking-tight leading-tight">
                BD Legal
              </div>
              <div className="text-[10px] font-semibold text-nav-text tracking-[0.12em] uppercase leading-tight mt-px">
                RAG
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="mx-3 h-px bg-nav-border shrink-0" />

        {/* Nav */}
        <nav aria-label="Main navigation" className="flex-1 px-2 py-3 flex flex-col gap-0.5 overflow-y-auto overflow-x-hidden">
          {NAV.map((item) => (
            <NavItem
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
              end={item.end}
              collapsed={collapsed}
              onNavigate={() => setDrawerOpen(false)}
            />
          ))}
        </nav>

        {/* Bottom — collapse toggle (hidden on mobile) */}
        {!isMobile && (
          <>
            <div className="mx-3 h-px bg-nav-border shrink-0" />
            <div
              className={cn(
                "flex shrink-0 h-11 items-center",
                collapsed ? "justify-center" : "px-2",
              )}
            >
              <button
                onClick={toggleCollapsed}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-2.5 py-2 text-[12px] font-medium text-nav-text",
                  "hover:bg-nav-active-bg/50 hover:text-nav-text-active transition-all w-full",
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
          </>
        )}
      </aside>

      {/* Mobile drawer backdrop */}
      {isMobile && drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50"
          onClick={() => setDrawerOpen(false)}
          onKeyDown={(e) => { if (e.key === "Escape") setDrawerOpen(false); }}
          role="presentation"
          aria-hidden="true"
        />
      )}

      {/* Main */}
      <div className={cn("flex flex-1 min-w-0 flex-col", isMobile ? "max-h-dvh" : "overflow-y-auto max-h-screen")}>
        {/* Top bar */}
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 lg:px-6 backdrop-blur-sm shrink-0">
          {isMobile && (
            <button
              ref={hamburgerRef}
              onClick={() => setDrawerOpen((o) => !o)}
              aria-label={drawerOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={drawerOpen}
              className="inline-flex items-center justify-center size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <i className={`ti text-sm ${drawerOpen ? "ti-x" : "ti-menu-2"}`} />
            </button>
          )}
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
        <main id="main-content" className={cn("p-4 lg:p-6", !isReader && "mx-auto w-full max-w-[1100px]")}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
