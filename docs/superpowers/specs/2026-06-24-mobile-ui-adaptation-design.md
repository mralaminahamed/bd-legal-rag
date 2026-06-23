# Mobile UI/UX Adaptation — Design Spec

**Date**: 2026-06-24
**Project**: BD Legal RAG Admin Console
**Approach**: Hybrid Progressive Enhancement
**Breakpoint system**: All responsive changes use `lg` (1024px) as the primary threshold — desktop layout at >=1024px, mobile adaptation below. Uses `max-md` (768px) only for tighter packing on small phones (theme grids, content padding). This is a single-tradeoff system: tablets in portrait (768-1024px) get desktop layout with slightly tighter padding.

---


## 1. Layout & Navigation (AppShell)

**Current**: Fixed sidebar at 220px (or 60px collapsed) on all screen sizes. No mobile navigation.

**Design**:
- **Desktop (>=lg, 1024px)**: Keep current sidebar behavior unchanged
- **Desktop (>=lg, 1024px)**: Sidebar visible (current behavior)
- **Mobile (<lg)**: Sidebar becomes an **off-canvas overlay drawer**
  - Fixed position `inset-y-0 left-0 z-40`, slides in/out via `-translate-x-full` / `translate-x-0`
  - Backdrop overlay (`fixed inset-0 bg-black/50 z-30`) when open
  - Closes on nav item click, backdrop click, or Escape key
  - Remove collapsed state on mobile (no value in a 60px hidden sidebar)
- **Header**: Add hamburger button (`ti-menu-2`) on the left side of header bar on mobile
- **Padding**: Header `px-6` → `max-lg:px-4`, Main content `p-6` → `max-lg:p-4`
- **Files affected**: `AppShell.tsx`

## 2. Acts Registry (ActsPage + SourcesRow)

**Current**: 8-column HTML table — impossible on mobile.

**Design**:
- **Desktop (>=lg)**: Keep current `<table>` layout
- **Mobile (<lg)**: Replace table with **card list**
  - Use a shared `useIsMobile()` hook (responsive detection in one place, not per-page) — renders `<div>` cards instead of `<table>`/`<tr>`/`<td>`
  - Each Act renders as a card with: name (bold), full name (truncated), year, status badge, BN/EN status pills, chunk count
  - Action buttons (Read, Ingest/Stop) at card bottom, always visible on mobile
  - Expandable detail section for BN/EN run details (same expanded state as current chevron toggle)
  - Search bar stays, full width on mobile
  - SourcesRow component conditionally returns either `<tr>` or `<div>` based on a `mobile` prop passed from ActsPage
- **Stat cards**: Already responsive `grid-cols-2 sm:grid-cols-3` — reduce padding on mobile only
- **Files affected**: `ActsPage.tsx`, `SourcesRow.tsx`

## 3. Act Reader (ActReaderPage)

**Current**: Two persistent sidebars (AppShell + TOC), content area with excessive padding.

**Design**:
- **Desktop (>=lg)**: Keep current TOC sidebar with collapse toggle
- **Mobile (<lg)**: TOC becomes a **slide-in drawer from left** (consistent with AppShell)
  - Triggered by a "Contents" button in the sticky top bar
  - Same backdrop + close-on-tap pattern
  - `-mx-6 -my-6` negative margin layout collapses to single column
- **Content area**: `px-10` → `max-lg:px-6 max-md:px-4`, `py-10` → `max-lg:py-6`
- **Previous/Next bar**: Stays at bottom. On mobile, hide section titles (only show "§number" labels). Same icon + label pattern already exists with `hidden sm:inline` classes — extend to `max-lg:hidden`
- **Files affected**: `ActReaderPage.tsx`

## 4. Playground (PlaygroundPage)

**Current**: Header actions overflow, model+act selects overflow input bar, provider badge can be very long.

**Design**:
- **Header**: On mobile, show only New chat button and a "more" button (`ti-dots-vertical`) that opens a positioned `<div>` overlay (same pattern as ThemeToggle dropdown — positioned `absolute right-0 top-full` dropdown card) containing History link and Delete action
- **Input area**: Selects stack vertically on mobile instead of side-by-side:
  ```
  [Textarea - full width]
  [Model select     - full width]
  [Act filter       - full width]
  [⌘↵ hint                       Send]
  ```
- **Files affected**: `PlaygroundPage.tsx`

## 5. Dashboard + Threads + Settings

### Dashboard
- **Stat cards**: `grid-cols-2` mobile — no change needed
- **Recent queries**: On mobile, each row shows: query ID (truncated 8 chars) + query text (truncated, flex-1) + latency. Badges (declined/cached/degraded), confidence, language, and date are hidden on mobile. Play button is always visible — replace `opacity-0 group-hover:opacity-100` with `opacity-60` base and `hover:opacity-100` (or just `opacity-100` on mobile via responsive class)
- **Service health**: Already responsive stacking — fine

### Threads
- **Hover-only delete**: Add `group-active:opacity-100` and `group-focus-visible:opacity-100` for touch support
- Layout is already card-like and works on mobile

### Settings
- **Provider table**: 3 columns — wrap in `overflow-x-auto` (Table component already has this)
- **Theme picker**: Light grid `grid-cols-3` → `max-lg:grid-cols-2`. Dark grid `grid-cols-4` → `max-lg:grid-cols-3 max-md:grid-cols-2`
- **ThemeToggle dropdown**: `w-72` → `max-lg:right-0 max-lg:left-auto max-lg:w-[calc(100dvw-32px)]`, theme grids inside change to 2-col on mobile
- **Files affected**: `DashboardPage.tsx`, `ThreadsPage.tsx`, `SettingsPage.tsx`, `ThemeToggle.tsx`, `ThemePicker.tsx`

## 6. Global Patterns

All pages:

| Pattern | Current | Mobile Fix |
|---------|---------|------------|
| Main content padding | `p-6` | `max-lg:p-4` |
| Header padding | `px-6` | `max-lg:px-4` |
| Card internal padding | `px-5 py-4` | `max-lg:px-4 max-lg:py-3` |
| Hover-only reveals | `opacity-0 group-hover:opacity-100` | Add `group-active:opacity-100 group-focus-visible:opacity-100` |
| Small touch targets | `size-7` (28px) icon buttons | **Minimum 44×44px** — wrap in `<button className="p-2 -m-2">` to extend hit area without increasing visual size |
| Tables (remaining) | HTML tables (`Settings` providers table) | Already wrapped in `overflow-x-auto` via Table component — verify no regressions |
| Select overflow | Unconstrained | Add `max-w-full` to prevent overflow |

- **Files affected**: `AppShell.tsx`, `table.tsx`, `stat-card.tsx`, `ConnectionBadge.tsx`

## 7. Cross-Cutting UX Improvements (from UI/UX Pro Max review)

### 7a. Fix `100vh` on mobile (Playground)
- **Problem**: `h-[calc(100vh-6rem)]` on Playground — mobile browser chrome (URL bar) is included in 100vh, causing content to extend below the viewport
- **Fix**: Replace with `min-h-dvh` (dynamic viewport height) — or use `min-h-[calc(100dvh-6rem)]` for Tailwind v4
- **File**: `PlaygroundPage.tsx:498`

### 7b. Eliminate 300ms tap delay
- **Problem**: Mobile browsers add 300ms delay between tap and click on untagged touch elements
- **Fix**: Add to `globals.css` base layer:
  ```css
  html { touch-action: manipulation; }
  ```
- **File**: `globals.css`

### 7c. Prevent pull-to-refresh interference
- **Problem**: Pages with custom scroll containers (Dashboard auto-refresh, Playground message list) can conflict with browser pull-to-refresh
- **Fix**: Add `overscroll-behavior: contain` to the main scroll container on mobile
- **File**: `globals.css` — add as utility class or on `#root` container

### 7d. Drawer focus management (hamburger + TOC)
- **Problem**: When drawer opens, keyboard focus stays on the trigger button; user can tab "behind" the overlay
- **Fix**: When drawer opens, move focus to the first focusable element inside the drawer. When drawer closes, return focus to the trigger button. Use `aria-modal="true"` and `role="dialog"` on the drawer container.
- **File**: `AppShell.tsx`, `ActReaderPage.tsx`

### 7e. Touch target spacing
- **Problem**: Tightly packed icon buttons in headers (ThemeToggle, ConnectionBadge, hamburger) can cause mis-taps
- **Fix**: Ensure minimum **8px gap** between adjacent touch targets. Already using `gap-3` in header bar — verify on mobile.
- **File**: `AppShell.tsx` (header gap)

### 7f. Shared responsive hook
- **Problem**: Without a shared hook, each page implements its own `useMediaQuery` or CSS-based mobile detection — duplicated, inconsistent
- **Fix**: Create `useIsMobile()` hook that listens for `<lg` (1024px) breakpoint. All pages use this single source of truth:
  ```ts
  function useIsMobile(): boolean {
    const mq = window.matchMedia("(max-width: 1023px)");
    const [match, setMatch] = useState(mq.matches);
    useEffect(() => {
      const handler = (e: MediaQueryListEvent) => setMatch(e.matches);
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }, []);
    return match;
  }
  ```
- **File**: New `src/lib/useIsMobile.ts`

### 7g. Fix `100vh` in all containers (not just Playground)
- **Problem**: `max-h-screen` in AppShell (line 163) and `max-h-[calc(100vh-56px)]` in ActReader (line 225) have same mobile browser chrome issue
- **Fix**: Replace `max-h-screen` → `max-h-dvh` and `max-h-[calc(100vh-56px)]` → `max-h-[calc(100dvh-56px)]`
- **Files**: `AppShell.tsx:163`, `ActReaderPage.tsx:225`

### 7h. Fix nested scroll containers
- **Problem**: AppShell's main area has `overflow-y-auto max-h-screen`. Playground has `h-[calc(100vh-6rem)]` with its own `overflow-y-auto`. This creates nested scroll regions — on mobile the inner scroll can fight with the outer scroll.
- **Fix**: On Playground page, remove the outer `overflow-y-auto` from AppShell main container when on mobile (let the page control its own scroll). Or remove inner scroll from Playground and let the AppShell handle it.
- **File**: `AppShell.tsx`, `PlaygroundPage.tsx`

### 7j. Review empty states on mobile
- **Problem**: All pages have empty states (Dashboard "No queries yet", Acts "No acts registered", Threads "No conversations yet", Playground empty state). These use centered icons + text + buttons — must verify they fit viewport without overflow
- **Fix**: On mobile, reduce icon sizes (`text-2xl` → `text-xl`), reduce vertical padding (`py-12/20` → `py-8`), ensure CTAs are full-width touch targets
- **Files**: `DashboardPage.tsx` (line 199-203), `ActsPage.tsx` (line 186-194), `ThreadsPage.tsx` (lines 120-144), `PlaygroundPage.tsx` (lines 586-615)

### 7k. ActsPage search bar: full width on mobile
- **Problem**: Search input is wrapped in `max-w-sm` (384px) — too narrow for mobile
- **Fix**: Change to `max-lg:max-w-full`
- **File**: `ActsPage.tsx:147`

### 7l. ActsPage stat cards: specify padding reduction
- **Problem**: "Reduce padding on mobile" is vague
- **Fix**: `p-4` → `max-lg:p-3` in `StatCard` component — consistent with global card padding change
- **File**: `stat-card.tsx`, `ActsPage.tsx`

### 7m. Verify ConnectionBadge on mobile header
- **Problem**: Header has hamburger (left), ConnectionBadge + ThemeToggle (right). On mobile with stacked elements, the header may feel crowded
- **Fix**: ConnectionBadge already uses `text-[11px]` with compact pill styling. On mobile, consider using the `collapsed` variant (just a colored dot) when screen is very narrow. Also add the badge to the sidebar drawer nav area so it's accessible there.
- **File**: `AppShell.tsx` (header), `ConnectionBadge.tsx`

### 7n. Mobile-first breakpoint approach
- **Note**: All changes use `max-*` (max-width) breakpoints, which is desktop-first. True mobile-first would use default mobile styles + `lg:` overrides. This is a **conscious trade-off** — the existing codebase has no mobile styles, so adding `max-*` overrides is the pragmatic path with minimal regression risk.
- **Future**: When the design system is revisited, consider flipping to mobile-first defaults.

## 8. Files Summary

| File | Changes |
|------|---------|
| `useIsMobile.ts` (new) | Shared `useIsMobile()` hook for responsive detection |
| `AppShell.tsx` | Hamburger drawer on <lg, focus management, nested scroll fix, responsive padding |
| `ActsPage.tsx` | Card layout on <lg, full-width search on mobile, empty state mobile review |
| `SourcesRow.tsx` | Accept `mobile` prop, render `<div>` card instead of `<tr>` when true |
| `ActReaderPage.tsx` | TOC drawer on <lg, focus management, 100dvh fix, responsive padding |
| `PlaygroundPage.tsx` | Responsive header, stacked selects on mobile, 100dvh fix, nested scroll fix |
| `DashboardPage.tsx` | Responsive query list, hover fix, empty state mobile review |
| `ThreadsPage.tsx` | Touch-compatible delete button, empty state mobile review |
| `SettingsPage.tsx` | Responsive theme grids |
| `ThemePicker.tsx` | Responsive grid columns |
| `ThemeToggle.tsx` | Responsive dropdown width + grids |
| `globals.css` | `touch-action: manipulation`, `overscroll-behavior: contain` |
| `table.tsx` | Overflow scroll guarantee |
| `stat-card.tsx` | Responsive padding on mobile |
| `ConnectionBadge.tsx` | Optional compact dot-only variant for narrow headers |

---

## 9. Non-Goals

- No changes to backend API, data fetching, or routing
- No layout changes on desktop (`>=lg`)
- No new dependencies
- No functional changes — adaptation only
