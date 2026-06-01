import { useState, useRef, useEffect } from "react";
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

const UI_STRINGS = {
  en: {
    placeholder: "Ask a legal question in Bengali or English…",
    send: "Ask",
    sending: "Thinking…",
    disclaimer_label: "Legal Disclaimer",
    declined: "This question requires legal advice. Please consult a qualified lawyer.",
    empty_title: "Ask a legal question",
    empty_sub: "Search across Bangladeshi statute law — Labour, Tax, VAT, Digital Security, Companies Acts.",
  },
  bn: {
    placeholder: "বাংলা বা ইংরেজিতে আইনি প্রশ্ন জিজ্ঞাসা করুন…",
    send: "জিজ্ঞাসা করুন",
    sending: "চিন্তা করছি…",
    disclaimer_label: "আইনি দায়মুক্তি",
    declined: "এই প্রশ্নের উত্তর দেওয়া সম্ভব নয় — একজন যোগ্য আইনজীবীর পরামর্শ নিন।",
    empty_title: "আইনি প্রশ্ন জিজ্ঞাসা করুন",
    empty_sub: "বাংলা বা ইংরেজিতে বাংলাদেশের আইন অনুসন্ধান করুন।",
  },
} as const;

type UILang = "en" | "bn";

interface FinalResult {
  answer: string;
  disclaimer: string | null;
  cached: boolean;
  degraded: boolean;
  declined: boolean;
}

const EXAMPLE_QUESTIONS = [
  "What is the weekly holiday entitlement under the Labour Act?",
  "What constitutes digital security offences?",
  "শ্রম আইনে কর্মীর সাপ্তাহিক ছুটির বিধান কী?",
  "How many directors does a public company require?",
];

export function PlaygroundPage() {
  const [question, setQuestion] = useState("");
  const [actSlug, setActSlug] = useState<string>("");
  const [uiLang, setUiLang] = useState<UILang>("en");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [result, setResult] = useState<FinalResult | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const actsQ = useQuery({ queryKey: ["acts"], queryFn: getActs, staleTime: Infinity });
  const s = UI_STRINGS[uiLang];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamText, result]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || streaming) return;

    setStreaming(true);
    setStreamText("");
    setResult(null);

    try {
      const resp = await fetch(`${API_BASE_URL}/api/v1/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, act_slug: actSlug || null, language: null }),
      });

      if (!resp.ok || !resp.body) {
        setResult({ answer: "Error: could not reach the API.", disclaimer: null, cached: false, degraded: true, declined: false });
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
          if (event.type === "token" && event.text) setStreamText((p) => p + event.text);
          else if (event.type === "final") {
            setResult({ answer: event.answer ?? "", disclaimer: event.disclaimer, cached: event.cached, degraded: event.degraded, declined: event.declined });
            setStreamText("");
          }
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  // Strip the disclaimer that disclaimer.inject() appended to answer — shown separately below.
  const answerBody = result
    ? result.disclaimer && result.answer.includes(result.disclaimer)
      ? result.answer.slice(0, result.answer.lastIndexOf(result.disclaimer)).trimEnd()
      : result.answer
    : "";

  const hasContent = streaming || result;

  return (
    <div className="flex flex-col min-h-[calc(100vh-6rem)]">
      {/* Page header row */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Playground</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Bilingual legal Q&amp;A — Bangladesh statute law</p>
        </div>
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

      {/* Content */}
      <div className="flex-1">
        {!hasContent && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
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
        )}

        {/* Streaming */}
        {streaming && (
          <div className="mb-4">
            <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-5">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-border">
                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center">
                  <i className="ti ti-scale text-xs text-primary" />
                </div>
                <span className="text-xs font-semibold text-muted-foreground">BD Legal RAG</span>
                <div className="ml-auto flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                  <span className="text-xs text-primary">{s.sending}</span>
                </div>
              </div>
              {streamText ? (
                <div className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{streamText}</div>
              ) : (
                <div className="space-y-2.5 py-1">
                  <Skeleton className="h-3.5 w-3/4" />
                  <Skeleton className="h-3.5 w-full" />
                  <Skeleton className="h-3.5 w-1/2" />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-3 mb-4">
            <div className="rounded-xl ring-1 ring-foreground/10 bg-card p-5">
              <div className="flex items-center gap-2 mb-3 pb-3 border-b border-border">
                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center">
                  <i className="ti ti-scale text-xs text-primary" />
                </div>
                <span className="text-xs font-semibold text-muted-foreground">BD Legal RAG</span>
                <div className="ml-auto flex items-center gap-1.5">
                  {result.declined && <Badge variant="destructive"><i className="ti ti-ban text-[10px] mr-0.5" />Declined</Badge>}
                  {result.degraded && <Badge variant="warning"><i className="ti ti-alert-triangle text-[10px] mr-0.5" />Degraded</Badge>}
                  {result.cached && <Badge variant="accent"><i className="ti ti-bolt text-[10px] mr-0.5" />Cached</Badge>}
                </div>
              </div>
              {result.declined ? (
                <div className="flex items-start gap-3">
                  <i className="ti ti-scale-off text-base text-destructive mt-0.5" />
                  <p className="text-sm text-muted-foreground">{s.declined}</p>
                </div>
              ) : (
                <Markdown>{answerBody}</Markdown>
              )}
            </div>

            {result.disclaimer && (
              <div className="rounded-xl border border-warning/30 bg-warning/8 p-4">
                <div className="flex items-start gap-2.5">
                  <i className="ti ti-info-circle text-warning text-base mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-warning mb-1">{s.disclaimer_label}</p>
                    <Markdown className="text-xs [&_p]:text-muted-foreground [&_p]:leading-relaxed [&_p]:mb-0">{result.disclaimer}</Markdown>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="sticky bottom-0 pt-4">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="rounded-xl ring-1 ring-foreground/10 bg-card focus-within:ring-ring/40 focus-within:ring-2 transition-all overflow-hidden">
            <Textarea
              ref={textareaRef}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void handleSubmit(e as unknown as React.FormEvent);
              }}
              placeholder={s.placeholder}
              rows={3}
              disabled={streaming}
              className="border-0 bg-transparent rounded-none focus:ring-0 text-sm px-4 pt-3 pb-2"
            />
            <div className="flex items-center gap-2 px-3 pb-2.5 pt-1">
              <Select
                value={actSlug}
                onChange={(e) => setActSlug(e.target.value)}
                disabled={streaming}
                className="h-7 text-xs w-44 bg-background"
              >
                <option value="">All Acts</option>
                {actsQ.data?.map((a) => (
                  <option key={a.slug} value={a.slug}>{a.short_name}</option>
                ))}
              </Select>
              <span className="text-[11px] text-muted-foreground ml-1">⌘↵ to send</span>
              <div className="ml-auto">
                <Button type="submit" disabled={streaming || !question.trim()} size="sm">
                  {streaming ? (
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
