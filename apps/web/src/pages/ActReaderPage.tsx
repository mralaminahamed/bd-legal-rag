import { useEffect, useCallback, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getActStructure, getSectionDetail } from "@/api/query";
import { useLang } from "@/lib/langContext";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import type { ProvisionTreeNode } from "@/types/api";
import { cn } from "@/lib/utils";

// ── Tree helpers ──────────────────────────────────────────────────────────────

/** Flatten a provision tree to a depth-first ordered list of all nodes. */
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

/** Readable section number: subsections/clauses → "103(2)(a)" style. */
function sectionLabel(node: ProvisionTreeNode): string {
  if (node.kind === "subsection" || node.kind === "clause") return `(${node.number})`;
  return node.number;
}

/** Depth indent level for TOC display. */
const KIND_DEPTH: Record<string, number> = {
  part: 0,
  chapter: 1,
  section: 2,
  subsection: 3,
  clause: 4,
};

// ── TOC node ──────────────────────────────────────────────────────────────────

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
        "w-full text-left flex items-start gap-1.5 px-2 py-1 rounded-md text-xs transition-colors",
        isActive
          ? "bg-primary/10 text-primary font-semibold"
          : hasText
            ? "text-muted-foreground hover:bg-muted hover:text-foreground"
            : "text-foreground/70 font-semibold cursor-default",
      )}
      style={{ paddingLeft: `${8 + depth * 12}px` }}
      disabled={!hasText}
    >
      {isActive && (
        <span className="w-1 h-1 rounded-full bg-primary mt-1.5 shrink-0" />
      )}
      <span className="truncate leading-snug">
        {node.kind === "part" || node.kind === "chapter"
          ? `${node.kind.charAt(0).toUpperCase() + node.kind.slice(1)} ${node.number}${node.title ? `: ${node.title}` : ""}`
          : `§${sectionLabel(node)}${node.title ? ` — ${node.title}` : ""}`}
      </span>
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ActReaderPage() {
  const { slug, sectionId } = useParams<{ slug: string; sectionId?: string }>();
  const navigate = useNavigate();
  const { uiLang } = useLang();
  const [tocOpen, setTocOpen] = useState(true);

  // Structure (TOC)
  const structureQ = useQuery({
    queryKey: ["act-structure", slug],
    queryFn: () => getActStructure(slug!),
    enabled: !!slug,
    staleTime: 300_000,
  });

  // Flat ordered list of all nodes (for prev/next)
  const flat = structureQ.data ? flattenTree(structureQ.data.tree) : [];
  // Only nodes with text (sections, subsections, clauses)
  const readable = flat.filter(
    (n) => n.kind === "section" || n.kind === "subsection" || n.kind === "clause",
  );

  // Redirect to first section if no sectionId
  useEffect(() => {
    if (!sectionId && readable.length > 0 && slug) {
      navigate(`/acts/${slug}/read/${readable[0].id}`, { replace: true });
    }
  }, [sectionId, readable, slug, navigate]);

  const currentIndex = readable.findIndex((n) => n.id === sectionId);
  const prev = currentIndex > 0 ? readable[currentIndex - 1] : null;
  const next = currentIndex < readable.length - 1 ? readable[currentIndex + 1] : null;

  // Section content
  const sectionQ = useQuery({
    queryKey: ["section", slug, sectionId],
    queryFn: () => getSectionDetail(slug!, sectionId!),
    enabled: !!slug && !!sectionId,
    staleTime: 300_000,
  });

  // Keyboard navigation
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

  // Scroll to top on section change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [sectionId]);

  const act = structureQ.data?.act;
  const section = sectionQ.data;
  const revision = section?.revisions.find((r) => r.language === uiLang)
    ?? section?.revisions[0];

  // Build "ask in playground" URL
  const askUrl = section
    ? `/playground/${crypto.randomUUID()}?q=${encodeURIComponent(
        `Explain ${section.hierarchy_path}`,
      )}`
    : null;

  return (
    <div className="flex min-h-[calc(100vh-48px)] -mx-6 -my-6">
      {/* TOC sidebar */}
      <aside
        className={cn(
          "shrink-0 border-r border-border bg-card flex flex-col transition-[width] duration-200 overflow-hidden",
          tocOpen ? "w-64" : "w-10",
        )}
      >
        {/* TOC header */}
        <div className="flex items-center gap-2 px-3 py-3 border-b border-border shrink-0">
          <button
            onClick={() => setTocOpen((o) => !o)}
            className="text-muted-foreground hover:text-foreground transition-colors"
            title={tocOpen ? "Close TOC" : "Open TOC"}
          >
            <i className={`ti ${tocOpen ? "ti-layout-sidebar-left-collapse" : "ti-layout-sidebar-left-expand"} text-sm`} />
          </button>
          {tocOpen && (
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide truncate">
              Contents
            </span>
          )}
        </div>

        {/* TOC tree */}
        {tocOpen && (
          <div className="flex-1 overflow-y-auto px-1 py-2 space-y-px">
            {structureQ.isLoading
              ? Array.from({ length: 12 }).map((_, i) => (
                  <Skeleton key={i} className="h-5 w-full rounded" />
                ))
              : flat.map((node) => (
                  <TocNode
                    key={node.id}
                    node={node}
                    currentId={sectionId}
                    onClick={(id) => navigate(`/acts/${slug}/read/${id}`)}
                  />
                ))}
          </div>
        )}
      </aside>

      {/* Content area */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Act header bar */}
        <div className="sticky top-0 z-10 bg-background/90 backdrop-blur-sm border-b border-border px-6 py-3 flex items-center gap-3 shrink-0">
          <Link
            to="/acts"
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            title="Back to Acts Registry"
          >
            <i className="ti ti-arrow-left text-sm" />
          </Link>
          <div className="flex-1 min-w-0">
            {act ? (
              <>
                <h1 className="text-[13px] font-bold text-foreground truncate leading-tight">
                  {act.full_name_en}
                </h1>
                <p className="text-[11px] text-muted-foreground">
                  Act {act.act_number} of {act.act_year}
                  {currentIndex >= 0 && readable.length > 0 && (
                    <> · §{currentIndex + 1} of {readable.length}</>
                  )}
                </p>
              </>
            ) : (
              <Skeleton className="h-4 w-64" />
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {askUrl && (
              <Link
                to={askUrl}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
              >
                <i className="ti ti-message-question text-xs" />
                Ask
              </Link>
            )}
          </div>
        </div>

        {/* Section content */}
        <div className="flex-1 px-8 py-8 max-w-3xl mx-auto w-full">
          {sectionQ.isLoading || !section ? (
            <div className="space-y-4">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
            </div>
          ) : (
            <>
              {/* Breadcrumb */}
              <p className="text-[11px] text-muted-foreground mb-4 leading-relaxed">
                {section.hierarchy_path
                  .split(" > ")
                  .map((part, i, arr) => (
                    <span key={i}>
                      <span className={i === arr.length - 1 ? "text-foreground font-medium" : ""}>
                        {part}
                      </span>
                      {i < arr.length - 1 && (
                        <span className="mx-1.5 text-border">›</span>
                      )}
                    </span>
                  ))}
              </p>

              {/* Section heading */}
              <div className="flex items-start gap-3 mb-6">
                <span className="text-2xl font-bold text-primary/30 tabular-nums shrink-0 leading-tight">
                  §{section.number}
                </span>
                <div>
                  {section.title && (
                    <h2 className="text-xl font-bold text-foreground leading-tight">
                      {section.title}
                    </h2>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant={revision?.language === "bn" ? "default" : "secondary"} className="text-[10px]">
                      {revision?.language === "bn" ? "Bengali (authoritative)" : "English (reference)"}
                    </Badge>
                    {revision?.translation_status === "reference_translation" && (
                      <span className="text-[10px] text-warning">reference translation</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Statutory text */}
              {revision ? (
                <div className="prose-legal text-sm text-foreground leading-[1.9] whitespace-pre-wrap">
                  {revision.text}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No text available in {uiLang === "bn" ? "Bengali" : "English"} for this section.
                </p>
              )}

              {/* Effective dates */}
              {revision && (
                <div className="mt-8 pt-4 border-t border-border flex items-center gap-4 text-[11px] text-muted-foreground">
                  <span>In force from: <span className="text-foreground">{revision.effective_from}</span></span>
                  {revision.effective_to && (
                    <span>Until: <span className="text-foreground">{revision.effective_to}</span></span>
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

        {/* Prev/Next navigation */}
        <div className="sticky bottom-0 bg-background/90 backdrop-blur-sm border-t border-border px-6 py-3 flex items-center justify-between shrink-0">
          <button
            onClick={() => prev && slug && navigate(`/acts/${slug}/read/${prev.id}`)}
            disabled={!prev}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              prev
                ? "text-foreground hover:bg-muted"
                : "text-muted-foreground/40 cursor-not-allowed",
            )}
          >
            <i className="ti ti-arrow-left text-sm" />
            <span className="hidden sm:inline">
              {prev ? `§${prev.number}${prev.title ? ` — ${prev.title}` : ""}` : "Beginning"}
            </span>
            {!prev && <span className="sm:hidden">Beginning</span>}
          </button>

          {/* Progress indicator */}
          {readable.length > 0 && currentIndex >= 0 && (
            <div className="flex items-center gap-2">
              <div className="h-1 w-32 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${((currentIndex + 1) / readable.length) * 100}%` }}
                />
              </div>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {currentIndex + 1}/{readable.length}
              </span>
            </div>
          )}

          <button
            onClick={() => next && slug && navigate(`/acts/${slug}/read/${next.id}`)}
            disabled={!next}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              next
                ? "text-foreground hover:bg-muted"
                : "text-muted-foreground/40 cursor-not-allowed",
            )}
          >
            <span className="hidden sm:inline">
              {next ? `§${next.number}${next.title ? ` — ${next.title}` : ""}` : "End"}
            </span>
            {!next && <span className="sm:hidden">End</span>}
            <i className="ti ti-arrow-right text-sm" />
          </button>
        </div>
      </div>
    </div>
  );
}
