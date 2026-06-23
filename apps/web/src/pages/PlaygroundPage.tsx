import { useState, useRef, useEffect, useCallback } from "react";
import { useIsMobile } from "@/lib/useIsMobile";
import { cn } from "@/lib/utils";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useLang } from "@/lib/langContext";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getActs, getThread, deleteThread } from "@/api/query";
import { getLLMOverride, setLLMOverride, clearLLMOverride, getProviderConfig } from "@/api/admin";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/ui/markdown";
import { API_BASE_URL } from "@/lib/config";
import type { StreamEvent, ProviderConfigResponse } from "@/types/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  question: string;
  answer: string;
  streamText: string;
  disclaimer: string | null;
  citations: string[];
  declined: boolean;
  cached: boolean;
  degraded: boolean;
  status: "streaming" | "done" | "error";
}

// ── i18n ──────────────────────────────────────────────────────────────────────

const UI_STRINGS = {
  en: {
    placeholder: "Ask a legal question in Bengali or English…",
    send: "Ask",
    sending: "Thinking…",
    disclaimer_label: "Legal Disclaimer",
    declined: "No relevant provisions were found for this query in the indexed Acts.",
    empty_title: "New legal conversation",
    empty_sub: "Search across 16 Bangladeshi statute laws — ask a question, request a summary, list sections, or ask for legal guidance.",
    new_chat: "New chat",
  },
  bn: {
    placeholder: "বাংলা বা ইংরেজিতে আইনি প্রশ্ন জিজ্ঞাসা করুন…",
    send: "জিজ্ঞাসা করুন",
    sending: "চিন্তা করছি…",
    disclaimer_label: "আইনি দায়মুক্তি",
    declined: "ইন্ডেক্স করা আইনে এই প্রশ্নের জন্য প্রাসঙ্গিক কোনো বিধান পাওয়া যায়নি।",
    empty_title: "নতুন আইনি কথোপকথন",
    empty_sub: "১৬টি বাংলাদেশী আইন জুড়ে অনুসন্ধান করুন — প্রশ্ন করুন, সারসংক্ষেপ চান, ধারার তালিকা দেখুন।",
    new_chat: "নতুন চ্যাট",
  },
} as const;

const EXAMPLE_QUESTIONS = [
  "What is the penalty for digital fraud under the DSA?",
  "Summarize the Labour Act 2006",
  "List sections of the Companies Act 1994",
  "Can my employer deduct wages without notice?",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function UserBubble({ question }: { question: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-xl rounded-br-sm bg-primary px-4 py-2.5">
        <p className="text-sm text-primary-foreground leading-relaxed">{question}</p>
      </div>
    </div>
  );
}

function AiBubble({
  msg,
  disclaimerLabel,
  declinedText,
  onFeedback,
  feedbackGiven,
}: {
  msg: Message;
  disclaimerLabel: string;
  declinedText: string;
  onFeedback: (msgId: string, rating: string) => void;
  feedbackGiven: Record<string, string>;
}) {
  const answerBody =
    msg.disclaimer && msg.answer.includes(msg.disclaimer)
      ? msg.answer.slice(0, msg.answer.lastIndexOf(msg.disclaimer)).trimEnd()
      : msg.answer;

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5 ring-1 ring-primary/10">
        <i className="ti ti-scale text-xs text-primary" />
      </div>

      <div className="flex-1 max-w-[88%] space-y-2.5">
        <div className="rounded-xl rounded-tl-sm ring-1 ring-foreground/10 bg-card p-4 shadow-sm">
          {msg.status === "done" && (msg.declined || msg.degraded || msg.cached) && (
            <div className="flex items-center gap-1.5 mb-2">
              {msg.declined && (
                <Badge variant="destructive">
                  <i className="ti ti-ban text-[10px] mr-0.5" />Declined
                </Badge>
              )}
              {msg.degraded && (
                <Badge variant="warning">
                  <i className="ti ti-alert-triangle text-[10px] mr-0.5" />Degraded
                </Badge>
              )}
              {msg.cached && (
                <Badge variant="accent">
                  <i className="ti ti-bolt text-[10px] mr-0.5" />Cached
                </Badge>
              )}
            </div>
          )}

          {msg.status === "streaming" && !msg.streamText && (
            <div className="flex items-center gap-3 py-2">
              <div className="relative">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                  <i className="ti ti-brain text-primary text-sm animate-pulse" />
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-primary/30 animate-ping" />
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-foreground">Analyzing</span>
                  <span className="flex gap-0.5">
                    <span className="w-1 h-1 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1 h-1 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1 h-1 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">Searching legal provisions...</p>
              </div>
            </div>
          )}

          {msg.status === "streaming" && msg.streamText && (
            <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
              {msg.streamText}
              <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-primary animate-pulse rounded-sm align-text-bottom" />
            </div>
          )}

          {msg.status === "done" && (
            msg.declined ? (
              <div className="flex items-start gap-2.5">
                <i className="ti ti-scale-off text-base text-destructive mt-0.5" />
                <p className="text-sm text-muted-foreground">{declinedText}</p>
              </div>
            ) : (
              <Markdown>{answerBody || msg.answer}</Markdown>
            )
          )}

          {msg.status === "error" && (
            <p className="text-sm text-destructive flex items-center gap-1.5">
              <i className="ti ti-alert-circle text-sm" />
              Failed to get a response. Please try again.
            </p>
          )}
        </div>

        {msg.status === "done" && msg.disclaimer && (
          <div className="rounded-xl border border-warning/30 bg-warning/8 px-4 py-3">
            <div className="flex items-start gap-2">
              <i className="ti ti-info-circle text-warning text-base mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-warning mb-1">{disclaimerLabel}</p>
                <Markdown className="text-xs [&_p]:text-muted-foreground [&_p]:leading-relaxed [&_p]:mb-0">
                  {msg.disclaimer}
                </Markdown>
              </div>
            </div>
          </div>
        )}

        {msg.status === "done" && !msg.declined && (
          <div className="flex items-center gap-1">
            <span className="text-[11px] text-muted-foreground mr-1">Helpful?</span>
            {feedbackGiven[msg.id] ? (
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <i className="ti ti-check text-xs text-success" />
                Thanks for the feedback
              </span>
            ) : (
              <>
                <button
                  onClick={() => onFeedback(msg.id, "helpful")}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-success transition-colors"
                  aria-label="Mark as helpful"
                  title="Helpful"
                >
                  <i className="ti ti-thumb-up text-xs" />
                </button>
                <button
                  onClick={() => onFeedback(msg.id, "not_helpful")}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-destructive transition-colors"
                  aria-label="Mark as not helpful"
                  title="Not helpful"
                >
                  <i className="ti ti-thumb-down text-xs" />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Strip disclaimer from end of answer — it's shown separately. */
function extractDisclaimer(answer: string): { body: string; disclaimer: string | null } {
  // The disclaimer always starts with "**Disclaimer:**" or "**দায়মুক্তি:**"
  const idx = answer.search(/\*\*(?:Disclaimer|দায়মুক্তি):/);
  if (idx === -1) return { body: answer, disclaimer: null };
  return {
    body: answer.slice(0, idx).trimEnd(),
    disclaimer: answer.slice(idx).trim(),
  };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function PlaygroundPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState(() => searchParams.get("q") ?? "");
  const [actSlug, setActSlug] = useState("");
  const { uiLang } = useLang();
  const [isStreaming, setIsStreaming] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, string>>({});

  const [currentProvider, setCurrentProvider] = useState("");
  const [currentModel, setCurrentModel] = useState("");
  const [providerConfig, setProviderConfig] = useState<ProviderConfigResponse | null>(null);
  const [modelSwitching, setModelSwitching] = useState(false);
  const [embeddingHint, setEmbeddingHint] = useState<string | null>(null);
  const isMobile = useIsMobile();
  const [moreOpen, setMoreOpen] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const deleteDialogRef = useRef<HTMLDialogElement>(null);
  const queryClient = useQueryClient();

  const deleteMut = useMutation({
    mutationFn: deleteThread,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      navigate("/threads");
    },
  });

  const actsQ = useQuery({ queryKey: ["acts"], queryFn: getActs, staleTime: Infinity });
  const s = UI_STRINGS[uiLang];

  // Fetch current LLM override and provider config on mount
  useEffect(() => {
    Promise.all([getLLMOverride(), getProviderConfig()]).then(([override, config]) => {
      setProviderConfig(config);
      if (override.source === "override") {
        setCurrentProvider(override.provider);
        setCurrentModel(override.model);
      } else {
        setCurrentProvider("");
        setCurrentModel(override.model);
      }
    }).catch(() => {
      // Silently fail — dropdown will show "Auto" only
    });
  }, []);

  // Clear ?q param after reading
  useEffect(() => {
    if (searchParams.get("q")) {
      setSearchParams({}, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load thread from server when threadId changes
  useEffect(() => {
    if (!threadId) return;
    setIsStreaming(false);

    getThread(threadId)
      .then((thread) => {
        const loaded: Message[] = thread.messages.map((m) => {
          const { body, disclaimer } = extractDisclaimer(m.answer ?? "");
          return {
            id: m.id,
            question: m.question,
            answer: m.answer ?? "",
            streamText: "",
            disclaimer,
            citations: [],
            declined: m.declined,
            cached: m.cached,
            degraded: m.degraded,
            status: "done" as const,
            ...(disclaimer ? { answer: body } : {}),
          };
        });
        setMessages(loaded);
        // Restore feedback state from server
        const restored: Record<string, string> = {};
        for (const m of thread.messages) {
          if (m.feedback_rating) restored[m.id] = m.feedback_rating;
        }
        setFeedbackGiven(restored);
      })
      .catch(() => {
        // New thread or fetch failed — start empty
        setMessages([]);
      });
  }, [threadId]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.streamText]);

  // Cancel streaming on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const startNewThread = useCallback(() => {
    navigate(`/playground/${crypto.randomUUID()}`);
    setTimeout(() => textareaRef.current?.focus(), 100);
  }, [navigate]);

  async function handleFeedback(msgId: string, rating: string) {
    setFeedbackGiven((prev) => ({ ...prev, [msgId]: rating }));
    try {
      await fetch(`${API_BASE_URL}/api/v1/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_id: msgId, rating }),
      });
    } catch {
      // fire-and-forget
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || isStreaming || !threadId) return;

    const msg: Message = {
      id: crypto.randomUUID(),
      question: question.trim(),
      answer: "",
      streamText: "",
      disclaimer: null,
      citations: [],
      declined: false,
      cached: false,
      degraded: false,
      status: "streaming",
    };

    setMessages((prev) => [...prev, msg]);
    setQuestion("");
    setIsStreaming(true);

    try {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const resp = await fetch(`${API_BASE_URL}/api/v1/query/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Correlation-ID": threadId,  // binds this message to the thread in DB
        },
        body: JSON.stringify({
          question: msg.question,
          act_slug: actSlug || null,
          language: uiLang,   // respect the user's explicit language selection
        }),
        signal: abortRef.current.signal,
      });

      if (!resp.ok || !resp.body) {
        setMessages((prev) =>
          prev.map((m) => (m.id === msg.id ? { ...m, status: "error" } : m)),
        );
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const json = line.slice(5).trim();
          if (!json) continue;
          let event: StreamEvent;
          try { event = JSON.parse(json) as StreamEvent; } catch { continue; }

          if (event.type === "token" && event.text) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msg.id
                  ? { ...m, streamText: m.streamText + (event.text ?? "") }
                  : m,
              ),
            );
          } else if (event.type === "final") {
            const { body, disclaimer } = extractDisclaimer(event.answer ?? "");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msg.id
                  ? {
                      ...m,
                      answer: body || event.answer || "",
                      disclaimer: disclaimer ?? event.disclaimer,
                      citations: event.citations ?? [],
                      declined: event.declined,
                      cached: event.cached,
                      degraded: event.degraded,
                      streamText: "",
                      status: "done",
                    }
                  : m,
              ),
            );
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setMessages((prev) =>
        prev.map((m) => (m.id === msg.id ? { ...m, status: "error" } : m)),
      );
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }

  async function handleModelChange(value: string) {
    setModelSwitching(true);
    setEmbeddingHint(null);
    try {
      if (value === "") {
        await clearLLMOverride();
        setCurrentProvider("");
      } else {
        const [provider, ...modelParts] = value.split(":::");
        const model = modelParts.join(":::");
        await setLLMOverride({ provider, model });
        setCurrentProvider(provider);
        setCurrentModel(model);

        const isOllama = provider === "ollama" || provider === "ollama_cloud";
        if (isOllama) {
          setEmbeddingHint(
            "Tip: Switch embedding to Ollama (768 dims) in Settings for a fully local setup.",
          );
        } else if (providerConfig?.embed_model === "embeddinggemma") {
          setEmbeddingHint(
            "Tip: Switch embedding to Cohere (1024 dims) in Settings for better multilingual retrieval.",
          );
        }
      }
    } catch {
      // Revert silently — state stays as-is on error
    } finally {
      setModelSwitching(false);
    }
  }

  const hasMessages = messages.length > 0;
  const shortId = threadId?.slice(0, 8) ?? "";

  return (
    <div className="flex flex-col h-[calc(100dvh-6rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Playground</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-muted-foreground">Bilingual legal Q&amp;A</p>
            <span className="text-border/50">·</span>
            <span
              className="font-mono text-[10px] text-muted-foreground/40 select-all cursor-text tracking-tight"
              title={`Thread: ${threadId ?? ""}`}
            >
              {shortId}
            </span>
            {currentProvider && (
              <>
                <span className="text-border/50">·</span>
                <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground bg-muted/60 border border-border/50 rounded-full px-2 py-0.5">
                  <i className="ti ti-cpu text-[9px]" />
                  {currentProvider} {currentModel}
                </span>
              </>
            )}
          </div>
        </div>

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
                <div className="absolute right-0 top-full mt-1 w-40 rounded-xl bg-card ring-1 ring-border shadow-xl z-50 p-1">
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
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/threads">
                <i className="ti ti-messages text-sm" />
                History
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => deleteDialogRef.current?.showModal()}
              aria-label="Delete this conversation"
            >
              <i className="ti ti-trash text-sm" />
            </Button>
            <Button variant="outline" size="sm" onClick={startNewThread}>
              <i className="ti ti-pencil-plus text-sm" />
              {s.new_chat}
            </Button>
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <dialog
        ref={deleteDialogRef}
        className="backdrop:bg-black/50 rounded-xl border border-border bg-card p-0 w-full max-w-sm shadow-xl"
        onClick={(e) => { if (e.target === deleteDialogRef.current) deleteDialogRef.current?.close(); }}
      >
        <div className="p-5 space-y-4">
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-foreground">Delete conversation</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              All messages in this conversation will be permanently deleted.
            </p>
          </div>
          {deleteMut.isError && (
            <p className="text-xs text-destructive">Failed to delete. Please try again.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => deleteDialogRef.current?.close()}
              disabled={deleteMut.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => { if (threadId) deleteMut.mutate(threadId); }}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Deleting..." : "Delete"}
            </Button>
          </div>
        </div>
      </dialog>

      {/* Thread */}
      <div className={cn("flex-1 min-h-0 pb-4", isMobile ? "" : "overflow-y-auto")}>
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center py-10 lg:py-16 text-center">
            <div className="relative mb-5">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center ring-1 ring-primary/10">
                <i className="ti ti-scale text-2xl text-primary" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-gradient-to-br from-primary/25 to-primary/10 flex items-center justify-center">
                <i className="ti ti-sparkles text-[10px] text-primary" />
              </div>
            </div>
            <h2 className="text-lg font-semibold text-foreground mb-1.5">{s.empty_title}</h2>
            <p className="text-sm text-muted-foreground max-w-md mb-8 leading-relaxed">{s.empty_sub}</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-2xl">
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="text-left p-3.5 rounded-xl ring-1 ring-foreground/10 bg-card hover:bg-muted/70 hover:ring-primary/20 transition-all duration-200 group"
                >
                  <div className="flex items-start gap-2.5">
                    <div className="w-6 h-6 rounded-md bg-muted group-hover:bg-primary/10 flex items-center justify-center shrink-0 mt-0.5 transition-colors">
                      <span className="text-[10px] font-medium text-muted-foreground group-hover:text-primary">{i + 1}</span>
                    </div>
                    <span className="text-xs text-muted-foreground group-hover:text-foreground leading-snug">
                      {q}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((msg, i) => (
              <div key={msg.id} className="space-y-3 animate-fade-in-up" style={{ animationDelay: `${i * 30}ms` }}>
                <UserBubble question={msg.question} />
                <AiBubble
                  msg={msg}
                  disclaimerLabel={s.disclaimer_label}
                  declinedText={s.declined}
                  onFeedback={handleFeedback}
                  feedbackGiven={feedbackGiven}
                />
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="sticky bottom-0 pt-3 bg-background">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="rounded-xl ring-1 ring-foreground/10 bg-card focus-within:ring-primary/30 focus-within:ring-2 focus-within:shadow-[0_0_0_3px] focus-within:shadow-primary/5 transition-all duration-200 overflow-hidden">
            <Textarea
              ref={textareaRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  void handleSubmit(e as unknown as React.FormEvent);
                }
              }}
              placeholder={s.placeholder}
              aria-label={s.placeholder}
              rows={3}
              disabled={isStreaming}
              className="border-0 bg-transparent rounded-none focus:ring-0 text-sm px-4 pt-3 pb-2 placeholder:text-muted-foreground/60"
            />
            <div className={cn("flex items-center gap-2 px-3 pb-2.5 pt-1", isMobile ? "flex-col items-stretch" : "")}>
              <Select
                value={currentProvider ? `${currentProvider}:::${currentModel}` : ""}
                onChange={(e) => void handleModelChange(e.target.value)}
                disabled={isStreaming || modelSwitching}
                aria-label="Select model"
                className={cn("h-7 text-xs bg-background", isMobile ? "w-full" : "w-48")}
              >
                <option value="">Auto (default)</option>
                {providerConfig &&
                  Object.entries(providerConfig.providers)
                    .filter(([, info]) => info.configured)
                    .map(([provider, info]) => (
                      <option key={provider} value={`${provider}:::${info.model}`}>
                        {provider} — {info.model}
                      </option>
                    ))}
              </Select>
              <Select
                value={actSlug}
                onChange={(e) => setActSlug(e.target.value)}
                disabled={isStreaming}
                aria-label="Filter by act"
                className={cn("h-7 text-xs bg-background", isMobile ? "w-full" : "w-44")}
              >
                <option value="">All Acts</option>
                {actsQ.data?.map((a) => (
                  <option key={a.slug} value={a.slug}>{a.short_name}</option>
                ))}
              </Select>
              <span className="text-[11px] text-muted-foreground ml-1">⌘↵ to send</span>
              {embeddingHint && (
                <span className="text-[11px] text-muted-foreground/80 ml-1 flex items-center gap-1">
                  <i className="ti ti-info-circle text-[10px]" />
                  {embeddingHint}
                </span>
              )}
              <div className={isMobile ? "self-end mt-1" : "ml-auto"}>
                <Button type="submit" disabled={isStreaming || !question.trim()} size="sm" className="transition-all duration-200 hover:shadow-md hover:shadow-primary/20">
                  {isStreaming ? (
                    <><i className="ti ti-loader-2 animate-spin text-sm" />{s.sending}</>
                  ) : (
                    <><i className="ti ti-send text-sm" />{s.send}</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
