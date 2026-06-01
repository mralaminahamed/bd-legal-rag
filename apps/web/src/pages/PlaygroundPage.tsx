import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getActs } from "@/api/query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Markdown } from "@/components/ui/markdown";
import { API_BASE_URL } from "@/lib/config";
import type { StreamEvent } from "@/types/api";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Message {
  id: string;
  question: string;
  answer: string;
  streamText: string;
  disclaimer: string | null;
  declined: boolean;
  cached: boolean;
  degraded: boolean;
  status: "streaming" | "done" | "error";
}

interface Thread {
  id: string;
  messages: Message[];
}

// ── i18n ──────────────────────────────────────────────────────────────────────

const UI_STRINGS = {
  en: {
    placeholder: "Ask a legal question in Bengali or English…",
    send: "Ask",
    sending: "Thinking…",
    disclaimer_label: "Legal Disclaimer",
    declined: "This question requires legal advice. Please consult a qualified lawyer.",
    empty_title: "New legal conversation",
    empty_sub: "Search across Bangladeshi statute law — Labour, Tax, VAT, Digital Security, Companies Acts.",
    new_chat: "New chat",
  },
  bn: {
    placeholder: "বাংলা বা ইংরেজিতে আইনি প্রশ্ন জিজ্ঞাসা করুন…",
    send: "জিজ্ঞাসা করুন",
    sending: "চিন্তা করছি…",
    disclaimer_label: "আইনি দায়মুক্তি",
    declined: "এই প্রশ্নের উত্তর দেওয়া সম্ভব নয় — একজন যোগ্য আইনজীবীর পরামর্শ নিন।",
    empty_title: "নতুন আইনি কথোপকথন",
    empty_sub: "বাংলা বা ইংরেজিতে বাংলাদেশের আইন অনুসন্ধান করুন।",
    new_chat: "নতুন চ্যাট",
  },
} as const;

type UILang = "en" | "bn";

const EXAMPLE_QUESTIONS = [
  "What is the weekly holiday entitlement under the Labour Act?",
  "What constitutes digital security offences?",
  "শ্রম আইনে কর্মীর সাপ্তাহিক ছুটির বিধান কী?",
  "How many directors does a public company require?",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function newThread(): Thread {
  return { id: crypto.randomUUID(), messages: [] };
}

function newMessage(question: string): Message {
  return {
    id: crypto.randomUUID(),
    question,
    answer: "",
    streamText: "",
    disclaimer: null,
    declined: false,
    cached: false,
    degraded: false,
    status: "streaming",
  };
}

// ── User bubble ───────────────────────────────────────────────────────────────

function UserBubble({ question }: { question: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-xl rounded-br-sm bg-primary px-4 py-2.5">
        <p className="text-sm text-primary-foreground leading-relaxed">{question}</p>
      </div>
    </div>
  );
}

// ── AI bubble ─────────────────────────────────────────────────────────────────

function AiBubble({
  msg,
  disclaimerLabel,
  declinedText,
}: {
  msg: Message;
  disclaimerLabel: string;
  declinedText: string;
}) {
  const answerBody =
    msg.disclaimer && msg.answer.includes(msg.disclaimer)
      ? msg.answer.slice(0, msg.answer.lastIndexOf(msg.disclaimer)).trimEnd()
      : msg.answer;

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
        <i className="ti ti-scale text-xs text-primary" />
      </div>

      <div className="flex-1 max-w-[88%] space-y-2.5">
        <div className="rounded-xl rounded-tl-sm ring-1 ring-foreground/10 bg-card p-4">
          {/* Status badges */}
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

          {/* Thinking skeleton (before first token) */}
          {msg.status === "streaming" && !msg.streamText && (
            <div className="space-y-2 py-0.5">
              <Skeleton className="h-3.5 w-3/4" />
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-1/2" />
            </div>
          )}

          {/* Streaming text */}
          {msg.status === "streaming" && msg.streamText && (
            <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
              {msg.streamText}
              <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-primary animate-pulse rounded-sm align-text-bottom" />
            </div>
          )}

          {/* Final answer */}
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

        {/* Disclaimer */}
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
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function PlaygroundPage() {
  const [thread, setThread] = useState<Thread>(newThread);
  const [question, setQuestion] = useState("");
  const [actSlug, setActSlug] = useState("");
  const [uiLang, setUiLang] = useState<UILang>("en");
  const [isStreaming, setIsStreaming] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const actsQ = useQuery({ queryKey: ["acts"], queryFn: getActs, staleTime: Infinity });
  const s = UI_STRINGS[uiLang];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread.messages.length, thread.messages[thread.messages.length - 1]?.streamText]);

  const startNewThread = useCallback(() => {
    setThread(newThread());
    setQuestion("");
    setIsStreaming(false);
    setTimeout(() => textareaRef.current?.focus(), 50);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || isStreaming) return;

    const msg = newMessage(question.trim());
    setThread((t) => ({ ...t, messages: [...t.messages, msg] }));
    setQuestion("");
    setIsStreaming(true);

    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: msg.question,
          act_slug: actSlug || null,
          language: null,
        }),
      });

      if (!resp.ok || !resp.body) {
        setThread((t) => ({
          ...t,
          messages: t.messages.map((m) =>
            m.id === msg.id ? { ...m, status: "error" } : m,
          ),
        }));
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
            setThread((t) => ({
              ...t,
              messages: t.messages.map((m) =>
                m.id === msg.id
                  ? { ...m, streamText: m.streamText + (event.text ?? "") }
                  : m,
              ),
            }));
          } else if (event.type === "final") {
            setThread((t) => ({
              ...t,
              messages: t.messages.map((m) =>
                m.id === msg.id
                  ? {
                      ...m,
                      answer: event.answer ?? "",
                      disclaimer: event.disclaimer,
                      declined: event.declined,
                      cached: event.cached,
                      degraded: event.degraded,
                      streamText: "",
                      status: "done",
                    }
                  : m,
              ),
            }));
          }
        }
      }
    } catch {
      setThread((t) => ({
        ...t,
        messages: t.messages.map((m) =>
          m.id === msg.id ? { ...m, status: "error" } : m,
        ),
      }));
    } finally {
      setIsStreaming(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }

  const hasMessages = thread.messages.length > 0;

  return (
    <div className="flex flex-col min-h-[calc(100vh-6rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Playground</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-muted-foreground">Bilingual legal Q&amp;A</p>
            {hasMessages && (
              <>
                <span className="text-border">·</span>
                <span
                  className="font-mono text-[11px] text-muted-foreground/50 select-all cursor-text"
                  title="Thread ID"
                >
                  {thread.id.slice(0, 8)}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasMessages && (
            <Button variant="outline" size="sm" onClick={startNewThread}>
              <i className="ti ti-pencil-plus text-sm" />
              {s.new_chat}
            </Button>
          )}
          {/* Language toggle */}
          <div className="flex items-center gap-1 bg-secondary rounded-lg p-1">
            {(["en", "bn"] as UILang[]).map((lang) => (
              <button
                key={lang}
                onClick={() => setUiLang(lang)}
                className={cn(
                  "px-3 py-1 rounded-md text-xs font-semibold transition-colors",
                  uiLang === lang
                    ? "bg-card text-foreground shadow-sm ring-1 ring-foreground/10"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {lang === "en" ? "English" : "বাংলা"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Thread content */}
      <div className="flex-1">
        {!hasMessages ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
              <i className="ti ti-scale text-xl text-primary" />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-1">{s.empty_title}</h2>
            <p className="text-sm text-muted-foreground max-w-sm mb-8">{s.empty_sub}</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="text-left p-3 rounded-xl ring-1 ring-foreground/10 bg-card hover:bg-muted transition-colors group"
                >
                  <div className="flex items-start gap-2">
                    <i className="ti ti-message-question text-sm text-muted-foreground group-hover:text-primary mt-0.5 transition-colors shrink-0" />
                    <span className="text-xs text-muted-foreground group-hover:text-foreground leading-snug">
                      {q}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="space-y-6 pb-4">
            {thread.messages.map((msg) => (
              <div key={msg.id} className="space-y-3">
                <UserBubble question={msg.question} />
                <AiBubble
                  msg={msg}
                  disclaimerLabel={s.disclaimer_label}
                  declinedText={s.declined}
                />
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Sticky input */}
      <div className="sticky bottom-0 pt-3 bg-background">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="rounded-xl ring-1 ring-foreground/10 bg-card focus-within:ring-ring/40 focus-within:ring-2 transition-all overflow-hidden">
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
              rows={3}
              disabled={isStreaming}
              className="border-0 bg-transparent rounded-none focus:ring-0 text-sm px-4 pt-3 pb-2"
            />
            <div className="flex items-center gap-2 px-3 pb-2.5 pt-1">
              <Select
                value={actSlug}
                onChange={(e) => setActSlug(e.target.value)}
                disabled={isStreaming}
                className="h-7 text-xs w-44 bg-background"
              >
                <option value="">All Acts</option>
                {actsQ.data?.map((a) => (
                  <option key={a.slug} value={a.slug}>{a.short_name}</option>
                ))}
              </Select>
              <span className="text-[11px] text-muted-foreground ml-1">⌘↵ to send</span>
              <div className="ml-auto">
                <Button
                  type="submit"
                  disabled={isStreaming || !question.trim()}
                  size="sm"
                >
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
