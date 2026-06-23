# Mobile UI/UX Adaptation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the BD Legal RAG admin console fully usable on mobile phones while preserving the desktop experience.

**Architecture:** Progressive enhancement — desktop layout unchanged at >=1024px (lg). Below that, add hamburger drawer, card-based tables, responsive inputs, touch-friendly targets, and global CSS fixes. Shared `useIsMobile()` hook centralizes responsive detection.

**Tech Stack:** React 19, TypeScript, Tailwind CSS v4, React Router v7, Tabler Icons

---

### Task 0: Create shared `useIsMobile` hook

**Files:**
- Create: `apps/web/src/lib/useIsMobile.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useState, useEffect } from "react";

const MOBILE_BREAKPOINT = 1023; // matches `max-lg` in Tailwind

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
  });

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return isMobile;
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd apps/web && npx tsc --noEmit src/lib/useIsMobile.ts` (or just `npm run type-check`)
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/useIsMobile.ts
git commit -m "feat: add useIsMobile shared hook for responsive detection"
```

---

### Task 1: Global CSS fixes (touch-action, overscroll)

**Files:**
- Modify: `apps/web/src/styles/globals.css`

- [ ] **Step 1: Add `touch-action: manipulation` and `overscroll-behavior`**

Add inside the `@layer base` block (after line 528 `html, body, #root { height: 100%; }`):

```css
  html {
    touch-action: manipulation;
  }
```

Add after the `scrollbar-width` section (around line 567):

```css
  /* Prevent pull-to-refresh on custom scroll containers */
  .scroll-container {
    overscroll-behavior: contain;
  }

  /* Prevent <select> from overflowing its container on mobile */
  select {
    max-width: 100%;
  }
```

- [ ] **Step 2: Verify the build works**

Run: `cd apps/web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/styles/globals.css
git commit -m "fix: add touch-action and overscroll-behavior for mobile"
```

---

### Task 2: Global patterns — stat-card, ConnectionBadge, hover-only reveals

**Files:**
- Modify: `apps/web/src/components/ui/stat-card.tsx`
- Modify: `apps/web/src/components/layout/ConnectionBadge.tsx`

- [ ] **Step 1: Make StatCard padding responsive**

In `apps/web/src/components/ui/stat-card.tsx`, line 27, change:
```tsx
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
```
To:
```tsx
    <div className="rounded-xl bg-card p-4 max-lg:p-3 ring-1 ring-foreground/10">
```

- [ ] **Step 2: Add compact (dot-only) variant to ConnectionBadge**

In `apps/web/src/components/layout/ConnectionBadge.tsx`, add a prop for compact mode:
```typescript
export function ConnectionBadge({ collapsed, compact }: { collapsed?: boolean; compact?: boolean }) {
```
Above the `if (collapsed)` check (around line 14), add:
```typescript
  if (compact) {
    return (
      <span
        title={ok ? "API online" : "API offline"}
        className={cn("w-2 h-2 rounded-full shrink-0", ok ? "bg-success" : "bg-destructive")}
      />
    );
  }
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/ui/stat-card.tsx apps/web/src/components/layout/ConnectionBadge.tsx
git commit -m "feat: responsive stat-card padding, compact ConnectionBadge variant"
```

---

### Task 3: AppShell — hamburger drawer + responsive padding + nested scroll fix

**Files:**
- Modify: `apps/web/src/components/layout/AppShell.tsx`

This is the largest change. Read the current file first, then apply edits.

- [ ] **Step 1: Import `useIsMobile` at top of AppShell.tsx**

Add after the existing imports (line 8):
```typescript
import { useIsMobile } from "@/lib/useIsMobile";
```

- [ ] **Step 2: Add drawer state to the component**

After `const location = useLocation();` (line 64), add:
```typescript
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);
```

- [ ] **Step 3: Close drawer on navigation**

Add to `NAV.map` callback's `NavItem` — when a nav item is clicked/tapped on mobile, close the drawer. The NavItem already receives an onClick — pass a close handler through the `to` prop. Instead, add `onClick` to each NavLink:

```typescript
function NavItem({
  to, label, icon, end, collapsed, onNavigate
}: {
  to: string; label: string; icon: string; end: boolean; collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      ...
```

In the `<nav>` rendering (line 121), pass `onNavigate={() => setDrawerOpen(false)}`:
```typescript
            <NavItem
              key={item.to}
              to={item.to}
              label={item.label}
              icon={item.icon}
              end={item.end}
              collapsed={collapsed}
              onNavigate={() => setDrawerOpen(false)}
            />
```

- [ ] **Step 4: Add hamburger button in header bar on mobile**

In the `<header>` element (line 165), add before the `<div className="flex-1" />`:
```typescript
          {isMobile && (
            <button
              onClick={() => setDrawerOpen((o) => !o)}
              aria-label={drawerOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={drawerOpen}
              className="inline-flex items-center justify-center size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <i className={`ti text-sm ${drawerOpen ? "ti-x" : "ti-menu-2"}`} />
            </button>
          )}
```

- [ ] **Step 5: Make header padding responsive**

Change line 165:
```tsx
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-6 backdrop-blur-sm shrink-0">
```
To:
```tsx
        <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 lg:px-6 backdrop-blur-sm shrink-0">
```

- [ ] **Step 6: Make main content padding responsive**

Change line 196:
```tsx
        <main id="main-content" className={cn("p-6", !isReader && "mx-auto w-full max-w-[1100px]")}>
```
To:
```tsx
        <main id="main-content" className={cn("p-4 lg:p-6", !isReader && "mx-auto w-full max-w-[1100px]")}>
```

- [ ] **Step 7: Wrap sidebar in responsive drawer overlay**

Replace the current `<aside>` block (lines 86-160) with this:

```tsx
      {/* Sidebar — desktop: fixed sidebar, mobile: overlay drawer */}
      <aside
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
```

- [ ] **Step 8: Add backdrop overlay when drawer open on mobile**

Before the `<aside>` closing tag (line 160 area), add:
```typescript
        {/* Mobile footer area — unchanged */}
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
```

- [ ] **Step 9: Remove collapsed toggle on mobile**

In the bottom collapse button section (lines 132-159), wrap the entire block with `{!isMobile && (`:
```typescript
        {!isMobile && (
          <>
            <div className="mx-3 h-px bg-nav-border shrink-0" />
            <div ...>
              <button ...>
                ...
              </button>
            </div>
          </>
        )}
```

- [ ] **Step 10: Fix 100vh → 100dvh on main container**

Change line 163:
```tsx
      <div className="flex flex-1 min-w-0 flex-col overflow-y-auto max-h-screen">
```
To:
```tsx
      <div className={cn("flex flex-1 min-w-0 flex-col", isMobile ? "max-h-dvh" : "overflow-y-auto max-h-screen")}>
```

On mobile, move `overflow-y-auto` to individual pages (Playground already has it). This fixes the nested scroll anti-pattern.

- [ ] **Step 11: Add focus management for the drawer**

Add a `useEffect` that traps focus when drawer opens:
```typescript
  const sidebarRef = useRef<HTMLDivElement>(null);
  const hamburgerRef = useRef<HTMLButtonElement>(null);
```

Add refs to the hamburger button (add `ref={hamburgerRef}`) and the `<aside>` sidebar (add `ref={sidebarRef}`).

```typescript
  useEffect(() => {
    if (!isMobile || !drawerOpen) return;
    // Focus first focusable element inside drawer
    const firstFocusable = sidebarRef.current?.querySelector<HTMLElement>(
      'a, button, [tabindex]:not([tabindex="-1"])',
    );
    firstFocusable?.focus();
  }, [isMobile, drawerOpen]);
```

```typescript
  // Return focus to hamburger when drawer closes
  useEffect(() => {
    if (!isMobile || drawerOpen) return;
    hamburgerRef.current?.focus();
  }, [isMobile, drawerOpen]);
```

- [ ] **Step 12: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 13: Commit**

```bash
git add apps/web/src/components/layout/AppShell.tsx
git commit -m "feat: mobile hamburger drawer with focus management, responsive padding, nested scroll fix"
```

---

### Task 4: AppShell — verify skip-link still works with drawer

**Files:**
- Modify: `apps/web/src/components/layout/AppShell.tsx`

- [ ] **Step 1: The skip-to-content link (line 79-84) targets `#main-content`. When drawer is open on mobile, the link is still visible. Ensure it has `z-50` so it appears above the backdrop. The existing code already has `z-50` — verified. Close drawer on skip-link click to avoid confusion.**

Add `onClick` handler to the skip link:
```typescript
      <a
        href="#main-content"
        onClick={() => setDrawerOpen(false)}
        ...
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/layout/AppShell.tsx
git commit -m "fix: skip-to-content closes mobile drawer"
```

---

### Task 5: Dashboard — responsive query list + hover fixes + empty state

**Files:**
- Modify: `apps/web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Import `useIsMobile`**

Add at top:
```typescript
import { useIsMobile } from "@/lib/useIsMobile";
```

- [ ] **Step 2: Add `isMobile` inside component**

Add inside `DashboardPage` function:
```typescript
  const isMobile = useIsMobile();
```

- [ ] **Step 3: Add CSS class for play button always-visible on mobile**

In the play button `<Link>` (line 237-243), change:
```tsx
              <Link
                to={replayUrl}
                title="Open in Playground"
                className="shrink-0 text-muted-foreground/30 hover:text-primary transition-colors opacity-0 group-hover:opacity-100"
              >
```
To:
```tsx
              <Link
                to={replayUrl}
                title="Open in Playground"
                className="shrink-0 text-muted-foreground/30 hover:text-primary transition-colors max-lg:opacity-60 max-lg:hover:opacity-100 opacity-0 group-hover:opacity-100"
              >
```

- [ ] **Step 4: Hide badges, confidence, language, date on mobile**

In the query row, wrap non-essential info items with `max-lg:hidden`. The current row structure (lines 215-244):
- `<span className="font-mono text-[10px]...">` — keep (ID is helpful)
- `<span className="min-w-0 flex-1 truncate...">` — keep (query text is primary)
- `<span className="text-[11px] uppercase font-mono...">` — **hide on mobile**: add `max-lg:hidden`
- `<ConfidenceBadge>` — **hide on mobile**: wrap in `<span className="max-lg:hidden">`
- `<div className="flex gap-1 shrink-0">` (badges) — **hide on mobile**: add `max-lg:hidden`
- `<span className="text-xs text-muted-foreground shrink-0 tabular-nums">` (latency) — keep
- `<span className="w-28 text-right...">` (date) — **hide on mobile**: add `max-lg:hidden`

- [ ] **Step 5: Empty state — reduce vertical padding on mobile**

In the empty state (around line 199), change:
```tsx
          <div className="flex flex-col items-center py-12 text-center text-muted-foreground">
```
To:
```tsx
          <div className="flex flex-col items-center py-8 lg:py-12 text-center text-muted-foreground">
```

- [ ] **Step 6: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/pages/DashboardPage.tsx
git commit -m "feat: responsive Dashboard query list, mobile hover fix, empty state"
```

---

### Task 6: Threads — touch-compatible delete + empty state

**Files:**
- Modify: `apps/web/src/pages/ThreadsPage.tsx`

- [ ] **Step 1: Fix hover-only delete button for touch**

In the delete button (line 186-195), change:
```tsx
                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
```
To:
```tsx
                  className="max-lg:opacity-60 max-lg:hover:opacity-100 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
```

- [ ] **Step 2: Empty state — reduce vertical padding on mobile**

In the empty state (line 131), change:
```tsx
        <div className="flex flex-col items-center justify-center py-20 text-center">
```
To:
```tsx
        <div className="flex flex-col items-center justify-center py-12 lg:py-20 text-center">
```

- [ ] **Step 3: Plus sign on thread items — make delete always tappable**

The delete button is inside a `<button>` wrapper for the whole thread card. The `onClick` stopPropagation on delete is already there (line 187). Verify it works on touch — the `stopPropagation` on the delete button click is fine.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/pages/ThreadsPage.tsx
git commit -m "feat: Threads touch-compatible delete, responsive empty state"
```

---

### Task 7: ActsPage — card layout + search + empty state

**Files:**
- Modify: `apps/web/src/pages/ActsPage.tsx`
- Modify: `apps/web/src/features/SourcesRow.tsx`

- [ ] **Step 1: Import `useIsMobile` in ActsPage**

```typescript
import { useIsMobile } from "@/lib/useIsMobile";
```

- [ ] **Step 2: Add `isMobile` inside component**

```typescript
  const isMobile = useIsMobile();
```

- [ ] **Step 3: Make search bar full width on mobile**

Change line 147:
```tsx
      <div className="relative max-w-sm">
```
To:
```tsx
      <div className="relative max-lg:max-w-full max-w-sm">
```

- [ ] **Step 4: Render card layout instead of table on mobile**

Wrap the `<Table>` block (lines 158-198) with a conditional:
```tsx
      {isMobile ? (
        /* Mobile card list */
        <div className="space-y-2">
          {actsQ.isLoading
            ? Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full rounded-xl" />
              ))
            : filtered.map((act) => (
                <SourcesRow key={act.id} act={act} mobile />
              ))}
          {!actsQ.isLoading && filtered.length === 0 && (
            <div className="flex flex-col items-center py-8 text-center text-muted-foreground">
              <i className="ti ti-books-off text-2xl mb-2" />
              <span className="text-sm">
                {search ? "No acts match your search" : "No acts registered"}
              </span>
            </div>
          )}
        </div>
      ) : (
        /* Desktop table — unchanged */
        <div className="rounded-xl ring-1 ring-foreground/10 overflow-hidden bg-card">
          <Table>...</Table>
        </div>
      )}
```

- [ ] **Step 5: Update SourcesRow to accept `mobile` prop and render card**

Modify the `SourcesRow` component signature:
```typescript
export function SourcesRow({ act, mobile }: SourcesRowProps & { mobile?: boolean }) {
```

Add a card rendering mode at the top of the component. When `mobile` is true, return:
```tsx
  if (mobile) {
    return (
      <div className="rounded-xl ring-1 ring-foreground/10 bg-card overflow-hidden">
        <div
          className="p-3 cursor-pointer"
          onClick={() => setExpanded((e) => !e)}
        >
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="text-sm font-medium text-foreground">{act.short_name}</div>
              <div className="text-[11px] text-muted-foreground truncate max-w-[200px]">{act.full_name_en}</div>
            </div>
            <Badge variant={act.status === "in_force" ? "success" : "secondary"}>
              {act.status}
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
            <span className="tabular-nums">{act.act_year}</span>
            <span className="text-border">·</span>
            <span>BN: <RunBadgeInline status={act.last_run_bn?.status ?? "never"} /></span>
            <span className="text-border">·</span>
            <span>EN: <RunBadgeInline status={act.last_run_en?.status ?? "never"} /></span>
            {chunksTotal > 0 && (
              <>
                <span className="text-border">·</span>
                <span>{chunksTotal.toLocaleString()} chunks</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {isIngested && (
              <Button size="sm" variant="ghost" asChild>
                <Link to={`/acts/${act.slug}/read`}><i className="ti ti-book text-sm" /> Read</Link>
              </Button>
            )}
            {isRunning ? (
              <Button size="sm" variant="destructive" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                <i className="ti ti-square-x text-sm" /> Stop
              </Button>
            ) : (
              <Button size="sm" variant="secondary" onClick={() => ingest.mutate()} disabled={ingest.isPending}>
                <i className="ti ti-refresh text-sm" /> Ingest
              </Button>
            )}
          </div>
        </div>
        {/* Expanded detail — same layout as desktop but simplified */}
        {expanded && (
          <div className="border-t border-border px-3 py-3 bg-muted/10">
            <div className="grid grid-cols-2 gap-3">
              {([{ lang: "Bengali", run: act.last_run_bn }, { lang: "English", run: act.last_run_en }] as const).map(({ lang, run }) => (
                <div key={lang}>
                  <p className="text-xs font-semibold text-muted-foreground mb-1">{lang}</p>
                  {run ? (
                    <div className="text-xs text-muted-foreground space-y-0.5">
                      <div className="flex items-center gap-1">
                        <RunBadgeInline status={run.status} />
                      </div>
                      <div>Started: {formatDateTime(run.started_at)}</div>
                      <div>{run.provisions_processed} provisions · {run.chunks_created} chunks</div>
                      {run.error && (
                        <div className="text-destructive bg-destructive/10 px-2 py-1 rounded-lg mt-1">{run.error}</div>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs italic text-muted-foreground">No runs yet</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }
```

Add a helper component `RunBadgeInline` inside SourcesRow:
```tsx
function RunBadgeInline({ status }: { status: string }) {
  if (status === "never") return <span className="text-muted-foreground">never</span>;
  if (status === "running") {
    return (
      <span className="inline-flex items-center gap-1 text-primary font-semibold">
        <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />running
      </span>
    );
  }
  const color = status === "succeeded" ? "text-success" : status === "failed" ? "text-destructive" : "text-muted-foreground";
  return <span className={color}>{status}</span>;
}
```

- [ ] **Step 6: Remove `px-5 py-4` borders on table header for mobile**

In ActsPage, the table header row has `TableHead` components with `px-3`. These don't need changes since the table is only rendered on desktop.

- [ ] **Step 7: Empty state — reduce padding on mobile**

The empty state inside the card layout (Task 7 Step 4) already uses `py-8`. Verify the table-based empty state also uses responsive padding (line 186):
```tsx
                <td colSpan={8} className="px-3 py-12 text-center">
```
Change to:
```tsx
                <td colSpan={8} className="px-3 py-8 lg:py-12 text-center">
```

- [ ] **Step 8: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/pages/ActsPage.tsx apps/web/src/features/SourcesRow.tsx
git commit -m "feat: responsive ActsPage card layout on mobile, SourcesRow mobile prop"
```

---

### Task 8: ActReader — TOC drawer + responsive padding + 100dvh

**Files:**
- Modify: `apps/web/src/pages/ActReaderPage.tsx`

- [ ] **Step 1: Import `useIsMobile`**

```typescript
import { useIsMobile } from "@/lib/useIsMobile";
```

- [ ] **Step 2: Add `isMobile` state**

```typescript
  const isMobile = useIsMobile();
  const [tocDrawerOpen, setTocDrawerOpen] = useState(false);
```

- [ ] **Step 3: Fix 100vh → 100dvh (two places)**

Line 144:
```tsx
    <div className="flex min-h-[calc(100vh-56px)] -mx-6 -my-6">
```
To:
```tsx
    <div className="flex min-h-[calc(100dvh-56px)] -mx-6 -my-6">
```

Line 225:
```tsx
      <div className="flex-1 min-w-0 flex flex-col overflow-y-auto max-h-[calc(100vh-56px)]">
```
To:
```tsx
      <div className="flex-1 min-w-0 flex flex-col max-lg:overflow-visible overflow-y-auto max-h-[calc(100dvh-56px)]">
```

- [ ] **Step 4: Make TOC a slide-in drawer on mobile**

Wrap the existing `<aside>` block (lines 146-222) with mobile detection:
```tsx
      {isMobile ? (
        <>
          {/* Mobile: TOC trigger button in top bar (move to sticky top bar) */}
          {/* TOC is rendered as a drawer, triggered by button in top bar */}
          <aside
            className={cn(
              "fixed inset-y-0 left-0 z-40 w-[260px] max-w-[85vw] bg-card border-r border-border flex flex-col transition-transform duration-200 overflow-hidden",
              tocDrawerOpen ? "translate-x-0" : "-translate-x-full",
            )}
            aria-modal={tocDrawerOpen ? "true" : undefined}
            role={tocDrawerOpen ? "dialog" : undefined}
          >
            {/* TOC header */}
            <div className="flex items-center px-3 gap-2 border-b border-border shrink-0 h-11">
              <button onClick={() => setTocDrawerOpen(false)} className="text-muted-foreground hover:text-foreground">
                <i className="ti ti-x text-sm" />
              </button>
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Contents</span>
            </div>
            {act && (
              <div className="px-3 py-2.5 border-b border-border/60 bg-muted/30 shrink-0">
                <p className="text-[11px] font-semibold text-foreground/80 leading-snug line-clamp-2">{act.short_name}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{act.act_number} · {act.act_year}</p>
              </div>
            )}
            <div className="flex-1 overflow-y-auto px-1 py-2 space-y-px">
              {structureQ.isLoading
                ? Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-5 w-full rounded mx-1" />)
                : flat.map((node) => (
                    <TocNode key={node.id} node={node} currentId={sectionId} onClick={(id) => {
                      navigate(`/acts/${slug}/read/${id}`);
                      setTocDrawerOpen(false);
                    }} />
                  ))}
            </div>
            {readable.length > 0 && currentIndex >= 0 && (
              <div className="shrink-0 px-3 py-2.5 border-t border-border/60">
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${((currentIndex + 1) / readable.length) * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{currentIndex + 1}/{readable.length}</span>
                </div>
              </div>
            )}
          </aside>
          {/* Backdrop */}
          {tocDrawerOpen && (
            <div className="fixed inset-0 z-30 bg-black/50" onClick={() => setTocDrawerOpen(false)} aria-hidden="true" />
          )}
        </>
      ) : (
        /* Desktop TOC sidebar — unchanged */
        <aside className={cn("shrink-0 border-r border-border bg-card flex flex-col transition-[width] duration-200 overflow-hidden", tocOpen ? "w-56" : "w-10")}>
          ...
        </aside>
      )}
```

- [ ] **Step 5: Add "Contents" button in sticky top bar on mobile**

In the top bar (around line 227), add the Contents button after the back link:
```typescript
          {isMobile && (
            <button
              onClick={() => setTocDrawerOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
            >
              <i className="ti ti-list text-xs" />
              Contents
            </button>
          )}
```

- [ ] **Step 6: Responsive content padding**

In the section content area (line 261), change:
```tsx
        <div className="flex-1 px-10 py-10 max-w-2xl w-full">
```
To:
```tsx
        <div className="flex-1 px-4 lg:px-10 py-6 lg:py-10 max-w-2xl w-full">
```

- [ ] **Step 7: Mobile prev/next bar — hide section titles on mobile**

Current code lines 375-377 and 392-394 already have `hidden sm:inline` — extend to `max-lg:hidden`:
```tsx
            <span className="hidden lg:inline max-w-[180px] truncate">
```

And:
```tsx
            <span className="hidden lg:inline max-w-[180px] truncate">
```

- [ ] **Step 8: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/pages/ActReaderPage.tsx
git commit -m "feat: responsive ActReader - TOC drawer on mobile, 100dvh, responsive padding"
```

---

### Task 9: Playground — responsive header + stacked selects + 100dvh + nested scroll

**Files:**
- Modify: `apps/web/src/pages/PlaygroundPage.tsx`

- [ ] **Step 1: Import `useIsMobile`**

```typescript
import { useIsMobile } from "@/lib/useIsMobile";
```

- [ ] **Step 2: Add `isMobile`**

```typescript
  const isMobile = useIsMobile();
```

- [ ] **Step 3: Fix 100vh → 100dvh**

Change line 498:
```tsx
    <div className="flex flex-col h-[calc(100vh-6rem)]">
```
To:
```tsx
    <div className="flex flex-col h-[calc(100dvh-6rem)]">
```

- [ ] **Step 4: Collapse header actions into "more" dropdown on mobile**

Wrap the Header actions (lines 524-543) with:
```tsx
        {isMobile ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={startNewThread}>
              <i className="ti ti-pencil-plus text-sm" /> {s.new_chat}
            </Button>
            <div className="relative">
              <button
                onClick={() => setMoreOpen(!moreOpen)}
                aria-label="More options"
                className="inline-flex items-center justify-center size-7 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <i className="ti ti-dots-vertical text-sm" />
              </button>
              {moreOpen && (
                <div className="absolute right-0 top-full mt-1 w-40 rounded-xl bg-card ring-1 ring-border shadow-xl z-50 p-1 animate-fade-in-up">
                  <Link
                    to="/threads"
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                    onClick={() => setMoreOpen(false)}
                  >
                    <i className="ti ti-messages text-sm" /> History
                  </Link>
                  <button
                    onClick={() => { setMoreOpen(false); deleteDialogRef.current?.showModal(); }}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors w-full text-left"
                  >
                    <i className="ti ti-trash text-sm" /> Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Desktop — unchanged */
          <div className="flex items-center gap-2">
            ...
          </div>
        )}
```

- [ ] **Step 5: Add `moreOpen` state**

```typescript
  const [moreOpen, setMoreOpen] = useState(false);
```

- [ ] **Step 6: Stack selects vertically on mobile**

In the input area (lines 655-701), wrap the selects row to stack on mobile:
```tsx
            <div className={cn("flex items-center gap-2 px-3 pb-2.5 pt-1", isMobile ? "flex-col items-stretch" : "")}>
              <Select
                value={currentProvider ? `${currentProvider}:::${currentModel}` : ""}
                onChange={(e) => void handleModelChange(e.target.value)}
                disabled={isStreaming || modelSwitching}
                aria-label="Select model"
                className={cn("h-7 text-xs bg-background", isMobile ? "w-full" : "w-48")}
              >
                ...
              </Select>
              <Select
                value={actSlug}
                onChange={(e) => setActSlug(e.target.value)}
                disabled={isStreaming}
                aria-label="Filter by act"
                className={cn("h-7 text-xs bg-background", isMobile ? "w-full" : "w-44")}
              >
                ...
              </Select>
              <span className="text-[11px] text-muted-foreground ml-1">⌘↵ to send</span>
              ...
              <div className={isMobile ? "" : "ml-auto"}>
                <Button type="submit" disabled={isStreaming || !question.trim()} size={isMobile ? "default" : "sm"}>
                  ...
                </Button>
              </div>
            </div>
```

- [ ] **Step 7: Fix nested scroll — remove inner scroll on mobile**

Change the thread container (line 584):
```tsx
      <div className="flex-1 min-h-0 overflow-y-auto pb-4">
```
To:
```tsx
      <div className={cn("flex-1 min-h-0 pb-4", isMobile ? "" : "overflow-y-auto")}>
```

- [ ] **Step 8: Empty state — reduce vertical padding on mobile**

Change line 586:
```tsx
          <div className="flex flex-col items-center justify-center py-16 text-center">
```
To:
```tsx
          <div className="flex flex-col items-center justify-center py-10 lg:py-16 text-center">
```

- [ ] **Step 9: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 10: Commit**

```bash
git add apps/web/src/pages/PlaygroundPage.tsx
git commit -m "feat: responsive Playground - stacked selects, 100dvh, nested scroll fix, more dropdown"
```

---

### Task 10: Settings — responsive theme grids + ThemeToggle dropdown

**Files:**
- Modify: `apps/web/src/pages/SettingsPage.tsx`
- Modify: `apps/web/src/components/ThemePicker.tsx`
- Modify: `apps/web/src/components/layout/ThemeToggle.tsx`

- [ ] **Step 1: ThemePicker — responsive grid columns**

In `apps/web/src/components/ThemePicker.tsx`:

Line 169: Change `grid-cols-3 gap-2.5` to `grid-cols-2 lg:grid-cols-3 gap-2.5`

Line 192: Change `grid-cols-4 gap-2.5` to `grid-cols-2 lg:grid-cols-4 gap-2.5`

- [ ] **Step 2: ThemeToggle dropdown — responsive width and theme grids**

In `apps/web/src/components/layout/ThemeToggle.tsx`:

Line 110: Change `w-72` to `max-lg:right-0 max-lg:w-[calc(100dvw-32px)] lg:w-72`

Line 119: Change `grid-cols-3 gap-1.5` to `grid-cols-2 lg:grid-cols-3 gap-1.5`

Line 141: Change `grid-cols-4 gap-1.5` to `grid-cols-2 lg:grid-cols-4 gap-1.5`

- [ ] **Step 3: TypeScript check**

Run: `cd apps/web && npm run type-check`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/pages/SettingsPage.tsx apps/web/src/components/ThemePicker.tsx apps/web/src/components/layout/ThemeToggle.tsx
git commit -m "feat: responsive theme grids and ThemeToggle dropdown on mobile"
```

---

### Task 11: Hover-only reveal sweep across all pages

**Files:**
- All `.tsx` files under `apps/web/src/`

- [ ] **Step 1: Search and fix all `opacity-0 group-hover:opacity-100` patterns**

```bash
rg -n "opacity-0.*group-hover:" apps/web/src/ --type tsx
```

For each match found (expect: Dashboard play button, Threads delete button, SourcesRow actions), apply the fix pattern:
```typescript
className="max-lg:opacity-60 max-lg:hover:opacity-100 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 ..."
```

- [ ] **Step 2: Search for any `onMouseEnter` used for visibility toggling (not common, but verify)**

```bash
rg -n "onMouseEnter\|onMouseLeave" apps/web/src/ --type tsx
```

Expected: Only in ThemeToggle/ThemePicker for theme preview hover — acceptable (visual preview, not primary interaction).

- [ ] **Step 3: Verify touch spacing — confirm all adjacent touch targets have >=8px gap**

Key locations to verify:
- AppShell header: uses `gap-3` (12px) ✓
- Dashboard query row actions: uses `gap-1` (4px) — the play button and badges are tightly packed. On mobile, badges are hidden so the play button has breathing room. Acceptable.
- Threads thread item actions: uses `gap-2` (8px) ✓
- Playground header: mobile "more" + New chat uses `gap-2` ✓

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "fix: sweep all hover-only touch patterns, verify touch spacing"
```

---

### Task 12: Final verification

- [ ] **Step 1: Full type check**

```bash
cd apps/web && npm run type-check
```
Expected: No TypeScript errors

- [ ] **Step 2: Full build**

```bash
cd apps/web && npm run build
```
Expected: Build succeeds with no errors

- [ ] **Step 3: Verify no regressions — check all changed files**

```bash
git diff --stat
```
Review the list of changed files and verify all 14 files from the spec are included:
- `src/lib/useIsMobile.ts` (new)
- `src/styles/globals.css`
- `src/components/ui/stat-card.tsx`
- `src/components/layout/ConnectionBadge.tsx`
- `src/components/layout/AppShell.tsx`
- `src/pages/DashboardPage.tsx`
- `src/pages/ThreadsPage.tsx`
- `src/pages/ActsPage.tsx`
- `src/features/SourcesRow.tsx`
- `src/pages/ActReaderPage.tsx`
- `src/pages/PlaygroundPage.tsx`
- `src/components/ThemePicker.tsx`
- `src/components/layout/ThemeToggle.tsx`

- [ ] **Step 4: Commit any final adjustments**

```bash
git add -A && git commit -m "chore: final mobile UI adaptation adjustments"
```
