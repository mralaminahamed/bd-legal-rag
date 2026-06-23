import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listThreads, deleteThread } from "@/api/query";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function ThreadsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);

  const threadsQ = useQuery({
    queryKey: ["threads"],
    queryFn: () => listThreads(50),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const deleteMut = useMutation({
    mutationFn: deleteThread,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      setPendingDelete(null);
    },
  });

  const threads = threadsQ.data?.threads ?? [];
  const total = threadsQ.data?.total ?? 0;

  function startNewThread() {
    navigate(`/playground/${crypto.randomUUID()}`);
  }

  function confirmDelete(e: React.MouseEvent, threadId: string, title: string) {
    e.stopPropagation();
    setPendingDelete({ id: threadId, title });
    dialogRef.current?.showModal();
  }

  function executeDelete() {
    if (!pendingDelete) return;
    deleteMut.mutate(pendingDelete.id);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Conversations"
        description={total > 0 ? `${total} thread${total === 1 ? "" : "s"}` : "No conversations yet"}
        actions={
          <Button size="sm" onClick={startNewThread}>
            <i className="ti ti-pencil-plus text-sm" />
            New conversation
          </Button>
        }
      />

      {/* Delete confirmation dialog */}
      <dialog
        ref={dialogRef}
        className="backdrop:bg-black/50 rounded-xl border border-border bg-card p-0 w-full max-w-sm shadow-xl"
        onClick={(e) => { if (e.target === dialogRef.current) dialogRef.current?.close(); }}
      >
        {pendingDelete && (
          <div className="p-5 space-y-4">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-foreground">Delete conversation</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                &ldquo;{pendingDelete.title}&rdquo; and all its messages will be permanently deleted.
              </p>
            </div>
            {deleteMut.isError && (
              <p className="text-xs text-destructive">Failed to delete. Please try again.</p>
            )}
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => dialogRef.current?.close()}
                disabled={deleteMut.isPending}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={executeDelete}
                disabled={deleteMut.isPending}
              >
                {deleteMut.isPending ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        )}
      </dialog>

      {/* Thread list */}
      {threadsQ.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : threadsQ.isError ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <i className="ti ti-alert-circle text-3xl text-destructive mb-3" />
          <p className="text-sm font-semibold text-foreground mb-1">Failed to load conversations</p>
          <p className="text-xs text-muted-foreground mb-4">Check your connection and try again.</p>
          <Button variant="outline" size="sm" onClick={() => threadsQ.refetch()}>
            <i className="ti ti-refresh text-sm" />
            Retry
          </Button>
        </div>
      ) : threads.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 lg:py-20 text-center">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
            <i className="ti ti-messages-off text-xl text-primary" />
          </div>
          <p className="text-sm font-semibold text-foreground mb-1">No conversations yet</p>
          <p className="text-sm text-muted-foreground mb-6">
            Start a conversation in the Playground.
          </p>
          <Button onClick={startNewThread}>
            <i className="ti ti-pencil-plus text-sm" />
            New conversation
          </Button>
        </div>
      ) : (
        <div className="space-y-1.5">
          {threads.map((thread) => (
            <button
              key={thread.thread_id}
              onClick={() => navigate(`/playground/${thread.thread_id}`)}
              aria-label={`Open conversation: ${thread.first_question}`}
              className="w-full flex items-start gap-3 px-4 py-3 rounded-xl ring-1 ring-foreground/10 bg-card hover:bg-muted transition-colors text-left group"
            >
              {/* Thread icon */}
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                <i className="ti ti-message-chatbot text-sm text-primary" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate leading-tight group-hover:text-primary transition-colors">
                  {thread.first_question}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[11px] text-muted-foreground tabular-nums">
                    {thread.message_count} message{thread.message_count === 1 ? "" : "s"}
                  </span>
                  {thread.detected_language && (
                    <>
                      <span className="text-border">·</span>
                      <span className={cn(
                        "text-[10px] font-mono uppercase font-semibold",
                        thread.detected_language === "bn" ? "text-primary/70" : "text-muted-foreground",
                      )}>
                        {thread.detected_language}
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Actions: time + delete + chevron */}
              <div className="shrink-0 flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-muted-foreground">
                  {relativeTime(thread.last_activity)}
                </span>
                <button
                  onClick={(e) => confirmDelete(e, thread.thread_id, thread.first_question)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); confirmDelete(e as any, thread.thread_id, thread.first_question); } }}
                  tabIndex={0}
                  role="button"
                  aria-label={`Delete conversation: ${thread.first_question}`}
                  className="max-lg:opacity-60 max-lg:hover:opacity-100 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 p-1 rounded-md hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                >
                  <i className="ti ti-trash text-xs" />
                </button>
                <i className="ti ti-chevron-right text-[11px] text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
