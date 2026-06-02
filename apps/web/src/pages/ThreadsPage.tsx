import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listThreads } from "@/api/query";
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

  const threadsQ = useQuery({
    queryKey: ["threads"],
    queryFn: () => listThreads(50),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const threads = threadsQ.data?.threads ?? [];
  const total = threadsQ.data?.total ?? 0;

  function startNewThread() {
    navigate(`/playground/${crypto.randomUUID()}`);
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

      {/* Thread list */}
      {threadsQ.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : threads.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
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

              {/* Time + chevron */}
              <div className="shrink-0 flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-muted-foreground">
                  {relativeTime(thread.last_activity)}
                </span>
                <i className="ti ti-chevron-right text-[11px] text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
