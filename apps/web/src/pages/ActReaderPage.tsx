import { useEffect, useCallback, useState } from "react";
import { useIsMobile } from "@/lib/useIsMobile";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getActStructure, getSectionDetail } from "@/api/query";
import { useLang } from "@/lib/langContext";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import type { ProvisionTreeNode } from "@/types/api";
import { cn } from "@/lib/utils";

function flattenTree(nodes: ProvisionTreeNode[]): ProvisionTreeNode[] {
  const out: ProvisionTreeNode[] = [];
  function walk(ns: ProvisionTreeNode[]) {
    for (const n of ns) {
      out.push(n);
      if (n.children.length) walk(n.children);
    }
  }
  walk(nodes);
  return out;
}

function sectionLabel(node: ProvisionTreeNode): string {
  if (node.kind === "subsection" || node.kind === "clause") return `(${node.number})`;
  return node.number;
}

const KIND_DEPTH: Record<string, number> = {
  part: 0,
  chapter: 1,
  section: 2,
  subsection: 3,
  clause: 4,
};

function TocNode({
  node,
  currentId,
  onClick,
}: {
  node: ProvisionTreeNode;
  currentId: string | undefined;
  onClick: (id: string) => void;
}) {
  const depth = KIND_DEPTH[node.kind] ?? 0;
  const isActive = node.id === currentId;
  const hasText = node.kind !== "part" && node.kind !== "chapter";

  return (
    <button
      onClick={() => hasText && onClick(node.id)}
      className={cn(
        "w-full text-left flex items-start gap-1.5 py-[5px] rounded-md text-[12px] transition-colors leading-snug",
        isActive
          ? "bg-primary/10 text-primary font-semibold"
          : hasText
            ? "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            : "text-foreground/60 font-semibold cursor-default mt-2 first:mt-0",
      )}
      style={{ paddingLeft: `${8 + depth * 10}px`, paddingRight: "8px" }}
      disabled={!hasText}
    >
      {isActive && (
        <span className="w-1 h-1 rounded-full bg-primary mt-[6px] shrink-0" />
      )}
      <span className="truncate">
        {node.kind === "part" || node.kind === "chapter"
          ? `${node.kind.charAt(0).toUpperCase() + node.kind.slice(1)} ${node.number}${node.title ? `: ${node.title}` : ""}`
          : `§${sectionLabel(node)}${node.title ? ` — ${node.title}` : ""}`}
      </span>
    </button>
  );
}

export function ActReaderPage() {
  const { slug, sectionId } = useParams<{ slug: string; sectionId?: string }>();
  const navigate = useNavigate();
  const { uiLang } = useLang();
  const [tocOpen, setTocOpen] = useState(true);
  const isMobile = useIsMobile();
  const [tocDrawerOpen, setTocDrawerOpen] = useState(false);

  const structureQ = useQuery({
    queryKey: ["act-structure", slug],
    queryFn: () => getActStructure(slug!),
    enabled: !!slug,
    staleTime: 300_000,
  });

  const flat = structureQ.data ? flattenTree(structureQ.data.tree) : [];
  const readable = flat.filter(
    (n) => n.kind === "section" || n.kind === "subsection" || n.kind === "clause",
  );

  useEffect(() => {
    if (!sectionId && readable.length > 0 && slug) {
      navigate(`/acts/${slug}/read/${readable[0].id}`, { replace: true });
    }
  }, [sectionId, readable, slug, navigate]);

  const currentIndex = readable.findIndex((n) => n.id === sectionId);
  const prev = currentIndex > 0 ? readable[currentIndex - 1] : null;
  const next = currentIndex < readable.length - 1 ? readable[currentIndex + 1] : null;

  const sectionQ = useQuery({
    queryKey: ["section", slug, sectionId],
    queryFn: () => getSectionDetail(slug!, sectionId!),
    enabled: !!slug && !!sectionId,
    staleTime: 300_000,
  });

  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        if (next && slug) navigate(`/acts/${slug}/read/${next.id}`);
      }
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        if (prev && slug) navigate(`/acts/${slug}/read/${prev.id}`);
      }
    },
    [prev, next, slug, navigate],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [sectionId]);

  const act = structureQ.data?.act;
  const section = sectionQ.data;
  const revision = section?.revisions.find((r) => r.language === uiLang)
    ?? section?.revisions[0];

  const askUrl = section
    ? `/playground/${crypto.randomUUID()}?q=${encodeURIComponent(
        `Explain ${section.hierarchy_path}`,
      )}`
    : null;

  return (
    <div className="flex min-h-[calc(100dvh-56px)] -mx-6 -my-6">
      {/* ── TOC panel ──────────────────────────────────────── */}
      {isMobile ? (
        <>
          {/* Mobile: TOC slide-in drawer */}
          <aside
            className={cn(
              "fixed inset-y-0 left-0 z-40 w-[260px] max-w-[85vw] bg-card border-r border-border flex flex-col transition-transform duration-200 overflow-hidden",
              tocDrawerOpen ? "translate-x-0" : "-translate-x-full",
            )}
            aria-modal={tocDrawerOpen ? "true" : undefined}
            role={tocDrawerOpen ? "dialog" : undefined}
          >
            {/* TOC header with close button */}
            <div className="flex items-center px-3 gap-2 border-b border-border shrink-0 h-11">
              <button onClick={() => setTocDrawerOpen(false)} className="text-muted-foreground hover:text-foreground">
                <i className="ti ti-x text-sm" />
              </button>
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Contents</span>
            </div>
            {/* Act name strip */}
            {act && (
              <div className="px-3 py-2.5 border-b border-border/60 bg-muted/30 shrink-0">
                <p className="text-[11px] font-semibold text-foreground/80 leading-snug line-clamp-2">{act.short_name}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{act.act_number} · {act.act_year}</p>
              </div>
            )}
            {/* TOC tree */}
            <div className="flex-1 overflow-y-auto px-1 py-2 space-y-px">
              {structureQ.isLoading
                ? Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-5 w-full rounded mx-1" />)
                : structureQ.isError ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center px-3">
                    <i className="ti ti-alert-circle text-xl text-destructive mb-2" />
                    <p className="text-xs text-muted-foreground">Failed to load structure</p>
                  </div>
                ) : flat.map((node) => (
                    <TocNode key={node.id} node={node} currentId={sectionId} onClick={(id) => {
                      navigate(`/acts/${slug}/read/${id}`);
                      setTocDrawerOpen(false);
                    }} />
                  ))}
            </div>
            {/* Progress bar */}
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
        <aside
          className={cn(
            "shrink-0 border-r border-border bg-card flex flex-col transition-[width] duration-200 overflow-hidden",
            tocOpen ? "w-56" : "w-10",
          )}
        >
          {/* TOC header */}
          <div className={cn(
            "flex items-center border-b border-border shrink-0 h-11",
            tocOpen ? "px-3 gap-2" : "justify-center",
          )}>
            <button
              onClick={() => setTocOpen((o) => !o)}
              className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
              aria-label={tocOpen ? "Collapse table of contents" : "Expand table of contents"}
            >
              <i className={`ti ${tocOpen ? "ti-layout-sidebar-left-collapse" : "ti-layout-sidebar-left-expand"} text-sm`} />
            </button>
            {tocOpen && (
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider truncate">
                Contents
              </span>
            )}
          </div>

          {/* Act name strip */}
          {tocOpen && act && (
            <div className="px-3 py-2.5 border-b border-border/60 bg-muted/30 shrink-0">
              <p className="text-[11px] font-semibold text-foreground/80 leading-snug line-clamp-2">
                {act.short_name}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {act.act_number} · {act.act_year}
              </p>
            </div>
          )}

          {/* TOC tree */}
          {tocOpen && (
            <div className="flex-1 overflow-y-auto px-1 py-2 space-y-px">
              {structureQ.isLoading
                ? Array.from({ length: 12 }).map((_, i) => (
                    <Skeleton key={i} className="h-5 w-full rounded mx-1" />
                  ))
                : structureQ.isError ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center px-3">
                    <i className="ti ti-alert-circle text-xl text-destructive mb-2" />
                    <p className="text-xs text-muted-foreground">Failed to load structure</p>
                  </div>
                ) : flat.map((node) => (
                    <TocNode
                      key={node.id}
                      node={node}
                      currentId={sectionId}
                      onClick={(id) => navigate(`/acts/${slug}/read/${id}`)}
                    />
                  ))}
            </div>
          )}

          {/* Progress bar at bottom of TOC */}
          {tocOpen && readable.length > 0 && currentIndex >= 0 && (
            <div className="shrink-0 px-3 py-2.5 border-t border-border/60">
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${((currentIndex + 1) / readable.length) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                  {currentIndex + 1}/{readable.length}
                </span>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* ── Content area ───────────────────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col max-lg:overflow-visible overflow-y-auto max-h-[calc(100dvh-56px)]">
        {/* Top bar */}
        <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border px-6 h-11 flex items-center gap-3 shrink-0">
          <Link
            to="/acts"
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            title="Back to Acts Registry"
          >
            <i className="ti ti-arrow-left text-sm" />
          </Link>
          {isMobile && (
            <button
              onClick={() => setTocDrawerOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
            >
              <i className="ti ti-list text-xs" />
              Contents
            </button>
          )}
          <div className="flex-1 min-w-0">
            {act ? (
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[13px] font-semibold text-foreground truncate">
                  {act.full_name_en}
                </span>
                <span className="text-[11px] text-muted-foreground shrink-0">
                  · Act {act.act_number} of {act.act_year}
                </span>
              </div>
            ) : (
              <Skeleton className="h-4 w-64" />
            )}
          </div>
          {askUrl && (
            <Link
              to={askUrl}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors shrink-0"
            >
              <i className="ti ti-message-question text-xs" />
              Ask
            </Link>
          )}
        </div>

        {/* Section content */}
        <div className="flex-1 px-4 lg:px-10 py-6 lg:py-10 max-w-2xl w-full">
          {sectionQ.isLoading || !section ? (
            sectionQ.isError ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <i className="ti ti-alert-circle text-3xl text-destructive mb-3" />
                <p className="text-sm font-semibold text-foreground mb-1">Failed to load section</p>
                <p className="text-xs text-muted-foreground">Try navigating to a different section.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <Skeleton className="h-6 w-48" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
              </div>
            )
          ) : (
            <>
              {/* Breadcrumb */}
              <p className="text-[11px] text-muted-foreground mb-5 leading-relaxed">
                {section.hierarchy_path
                  .split(" > ")
                  .map((part, i, arr) => (
                    <span key={i}>
                      <span className={i === arr.length - 1 ? "text-foreground/80 font-medium" : ""}>
                        {part}
                      </span>
                      {i < arr.length - 1 && (
                        <span className="mx-1.5 text-border">›</span>
                      )}
                    </span>
                  ))}
              </p>

              {/* Section heading */}
              <div className="flex items-start gap-4 mb-7">
                <span className="text-3xl font-bold text-primary/20 tabular-nums shrink-0 leading-none mt-1">
                  §{section.number}
                </span>
                <div className="min-w-0">
                  {section.title && (
                    <h2 className="text-xl font-bold text-foreground leading-tight">
                      {section.title}
                    </h2>
                  )}
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <Badge
                      variant={revision?.language === "bn" ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {revision?.language === "bn" ? "Bengali (authoritative)" : "English (reference)"}
                    </Badge>
                    {revision?.translation_status === "reference_translation" && (
                      <span className="text-[10px] text-warning font-medium">reference translation</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Statutory text */}
              {revision ? (
                <div className="text-[14px] text-foreground leading-[1.95] whitespace-pre-wrap font-[400]">
                  {revision.text}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No text available in {uiLang === "bn" ? "Bengali" : "English"} for this section.
                </p>
              )}

              {/* Footer: effective dates + bdlaws link */}
              {revision && (
                <div className="mt-10 pt-4 border-t border-border/60 flex items-center gap-5 text-[11px] text-muted-foreground">
                  <span>
                    In force from:{" "}
                    <span className="text-foreground font-medium">{revision.effective_from}</span>
                  </span>
                  {revision.effective_to && (
                    <span>
                      Until:{" "}
                      <span className="text-foreground font-medium">{revision.effective_to}</span>
                    </span>
                  )}
                  <a
                    href={revision.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto flex items-center gap-1 hover:text-primary transition-colors"
                  >
                    <i className="ti ti-external-link text-[10px]" />
                    bdlaws source
                  </a>
                </div>
              )}
            </>
          )}
        </div>

        {/* Prev / Next nav bar */}
        <div className="sticky bottom-0 bg-background/95 backdrop-blur-sm border-t border-border px-6 h-11 flex items-center justify-between shrink-0">
          <button
            onClick={() => prev && slug && navigate(`/acts/${slug}/read/${prev.id}`)}
            disabled={!prev}
            aria-label={prev ? `Go to previous section ${prev.number}` : "Beginning of document"}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium transition-colors",
              prev
                ? "text-foreground hover:bg-muted"
                : "text-muted-foreground/30 cursor-not-allowed",
            )}
          >
            <i className="ti ti-arrow-left text-xs" />
            <span className="hidden lg:inline max-w-[180px] truncate">
              {prev ? `§${prev.number}${prev.title ? ` — ${prev.title}` : ""}` : "Beginning"}
            </span>
            {!prev && <span className="lg:hidden text-[12px]">Beginning</span>}
          </button>

          <button
            onClick={() => next && slug && navigate(`/acts/${slug}/read/${next.id}`)}
            disabled={!next}
            aria-label={next ? `Go to next section ${next.number}` : "End of document"}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[12px] font-medium transition-colors",
              next
                ? "text-foreground hover:bg-muted"
                : "text-muted-foreground/30 cursor-not-allowed",
            )}
          >
            <span className="hidden lg:inline max-w-[180px] truncate">
              {next ? `§${next.number}${next.title ? ` — ${next.title}` : ""}` : "End"}
            </span>
            {!next && <span className="lg:hidden text-[12px]">End</span>}
            <i className="ti ti-arrow-right text-xs" />
          </button>
        </div>
      </div>
    </div>
  );
}
