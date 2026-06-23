# Mobile UI/UX Adaptation — Design Spec

**Date**: 2026-06-24
**Project**: BD Legal RAG Admin Console
**Approach**: Hybrid Progressive Enhancement

---

## 1. Layout & Navigation (AppShell)

**Current**: Fixed sidebar at 220px (or 60px collapsed) on all screen sizes. No mobile navigation.

**Design**:
- **Desktop (>=lg, 1024px)**: Keep current sidebar behavior unchanged
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
  - Each Act renders as a card with: name (bold), full name (truncated), year, status badge, BN/EN status pills, chunk count
  - Action buttons (Read, Ingest/Stop) at card bottom
  - Expandable detail row for BN/EN run details (same expanded state as current)
  - Search bar stays, full width on mobile
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
- **Content area**: `px-10` → `max-lg:px-5 max-sm:px-4`, `py-10` → `max-lg:py-6`
- **Previous/Next bar**: Stays at bottom, compact on mobile
- **Files affected**: `ActReaderPage.tsx`

## 4. Playground (PlaygroundPage)

**Current**: Header actions overflow, model+act selects overflow input bar, provider badge can be very long.

**Design**:
- **Header**: On mobile, show only New chat button and a "more" dropdown (`ti-dots-vertical`) containing History link and Delete action
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
- **Recent queries**: On mobile, each row shows: query ID (truncated 8 chars) + query text (truncated, flex-1) + latency. Badges (declined/cached/degraded), confidence, language, and date are hidden on mobile. Play button remains but is always visible (not hover-only)
- **Service health**: Already responsive stacking — fine

### Threads
- **Hover-only delete**: Add `group-active:opacity-100` and `group-focus-visible:opacity-100` for touch support
- Layout is already card-like and works on mobile

### Settings
- **Provider table**: 3 columns — wrap in `overflow-x-auto` (Table component already has this)
- **Theme picker**: Light grid `grid-cols-3` → `max-sm:grid-cols-2`. Dark grid `grid-cols-4` → `max-sm:grid-cols-2`
- **ThemeToggle dropdown**: `w-72` → `max-sm:w-[calc(100vw-32px)]`, theme grids inside become 2-col on mobile
- **Files affected**: `DashboardPage.tsx`, `ThreadsPage.tsx`, `SettingsPage.tsx`, `ThemeToggle.tsx`, `ThemePicker.tsx`

## 6. Global Patterns

All pages:

| Pattern | Current | Mobile Fix |
|---------|---------|------------|
| Main content padding | `p-6` | `max-lg:p-4` |
| Header padding | `px-6` | `max-lg:px-4` |
| Card internal padding | `px-5 py-4` | `max-sm:px-4 max-sm:py-3` |
| Hover-only reveals | `opacity-0 group-hover:opacity-100` | Add `group-active:opacity-100 group-focus-visible:opacity-100` |
| Small touch targets | `size-7` icon buttons | Add invisible tap padding or `min-h-[40px]` on mobile |
| Tables | HTML tables | Ensure `overflow-x-auto` wrapper on all |
| Select overflow | Unconstrained | Add `max-w-full` to prevent overflow |

- **Files affected**: `globals.css` (touch target utilities), `AppShell.tsx`, `table.tsx`

---

## Files Summary

| File | Changes |
|------|---------|
| `AppShell.tsx` | Hamburger drawer on <lg, responsive padding |
| `ActsPage.tsx` | Card layout on <lg, responsive stats |
| `SourcesRow.tsx` | Card rendering mode on <lg |
| `ActReaderPage.tsx` | TOC drawer on <lg, responsive padding |
| `PlaygroundPage.tsx` | Responsive header, stacked selects on mobile |
| `DashboardPage.tsx` | Responsive query list, hover fix |
| `ThreadsPage.tsx` | Touch-compatible delete button |
| `SettingsPage.tsx` | Responsive theme grids |
| `ThemePicker.tsx` | Responsive grid columns |
| `ThemeToggle.tsx` | Responsive dropdown width + grids |
| `table.tsx` | Overflow scroll guarantee |

---

## Non-Goals

- No changes to backend API, data fetching, or routing
- No layout changes on desktop (`>=lg`)
- No new dependencies
- No functional changes — adaptation only
