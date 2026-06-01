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
    degraded: "Answer generated in degraded mode — AI summary unavailable, provisions only.",
    cached: "Served from cache.",
    empty_title: "Ask a legal question",
    empty_sub: "Search across Bangladeshi statute law in Bengali or English.",
  },
  bn: {
    placeholder: "বাংলা বা ইংরেজিতে আইনি প্রশ্ন জিজ্ঞাসা করুন…",
    send: "জিজ্ঞাসা করুন",
    sending: "চিন্তা করছি…",
    disclaimer_label: "আইনি দায়মুক্তি",
    declined: "এই প্রশ্নের উত্তর দেওয়া সম্ভব নয় — একজন যোগ্য আইনজীবীর পরামর্শ নিন।",
    degraded: "অবনত মোডে উত্তর তৈরি হয়েছে।",
    cached: "ক্যাশ থেকে পরিবেশিত।",
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

export function PlaygroundPage() {
  const [question, setQuestion] = useState("");
  const [actSlug, setActSlug] = useState<string>("");
  const [uiLang, setUiLang] = useState<UILang>("en");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [result, setResult] = useState<FinalResult | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const actsQ = useQuery({
    queryKey: ["acts"],
    queryFn: getActs,
    staleTime: Infinity,
  });

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
        body: JSON.stringify({
          question,
          act_slug: actSlug || null,
          language: null,
        }),
      });

      if (!resp.ok || !resp.body) {
        setResult({
          answer: "Error: could not reach the API.",
          disclaimer: null,
          cached: false,
          degraded: true,
          declined: false,
        });
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
          try {
            event = JSON.parse(json) as StreamEvent;
          } catch {
            continue;
          }

          if (event.type === "token" && event.text) {
            setStreamText((prev) => prev + event.text);
          } else if (event.type === "final") {
            setResult({
              answer: event.answer ?? "",
              disclaimer: event.disclaimer,
              cached: event.cached,
              degraded: event.degraded,
              declined: event.declined,
            });
            setStreamText("");
          }
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      void handleSubmit(e as unknown as React.FormEvent);
    }
  }

  const hasContent = streaming || result;

  return (
    <div className="flex flex-col min-h-0 h-full">
      {/* Header */}
      <div className="border-b border-border bg-surface px-6 py-4 shrink-0 flex items-center justify-between sticky top-0 z-10">
        <div>
          <h1 className="text-[15px] font-bold text-text-1">Playground</h1>
          <p className="text-[12px] text-text-4 mt-0.5">
            Bilingual legal Q&A — Bangladesh statute law
          </p>
        </div>
        {/* UI language toggle */}
        <div className="flex items-center gap-1 bg-page rounded-lg p-1">
          {(["en", "bn"] as UILang[]).map((lang) => (
            <button
              key={lang}
              onClick={() => setUiLang(lang)}
              className={cn(
                "px-3 py-1 rounded-md text-[12px] font-semibold transition-colors",
                uiLang === lang
                  ? "bg-surface text-text-1 shadow-sm"
                  : "text-text-4 hover:text-text-2"
              )}
            >
              {lang === "en" ? "English" : "বাংলা"}
            </button>
          ))}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        {/* Empty state */}
        {!hasContent && (
          <div className="flex flex-col items-center justify-center h-full py-20 px-6">
            <div className="w-14 h-14 rounded-2xl bg-accent/10 flex items-center justify-center mb-5">
              <i className="ti ti-scale text-2xl text-accent" />
            </div>
            <h2 className="text-[15px] font-bold text-text-1 mb-1.5">{s.empty_title}</h2>
            <p className="text-sm text-text-4 text-center max-w-sm">{s.empty_sub}</p>

            {/* Example questions */}
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
              {[
                "What is the minimum wage under the Labour Act 2006?",
                "What are the penalties for VAT evasion?",
                "শ্রম আইনে কর্মীর সাপ্তাহিক ছুটির বিধান কী?",
                "What constitutes digital security offences?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="text-left p-3 rounded-lg border border-border bg-surface hover:border-accent/40 hover:bg-accent/[0.04] transition-colors group"
                >
                  <div className="flex items-start gap-2">
                    <i className="ti ti-message-question text-sm text-text-4 group-hover:text-accent mt-0.5 transition-colors shrink-0" />
                    <span className="text-[12px] text-text-2 group-hover:text-text-1 leading-snug">
                      {q}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Streaming answer */}
        {streaming && streamText && (
          <div className="p-6">
            <div className="max-w-3xl mx-auto">
              <div className="bg-surface border border-border rounded-[10px] p-5">
                <div className="flex items-center gap-2 mb-3 pb-3 border-b border-border">
                  <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center">
                    <i className="ti ti-scale text-xs text-accent" />
                  </div>
                  <span className="text-[12px] font-semibold text-text-3">BD Legal RAG</span>
                  <div className="ml-auto flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                    <span className="text-[11px] text-accent">{s.sending}</span>
                  </div>
                </div>
                <div className="text-sm text-text-1 whitespace-pre-wrap leading-relaxed">
                  {streamText}
                </div>
                <div className="mt-3 flex gap-2">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Final result */}
        {result && (
          <div className="p-6">
            <div className="max-w-3xl mx-auto space-y-3">
              {/* Answer card */}
              <div className="bg-surface border border-border rounded-[10px] p-5">
                <div className="flex items-center gap-2 mb-3 pb-3 border-b border-border">
                  <div className="w-6 h-6 rounded-full bg-accent/10 flex items-center justify-center">
                    <i className="ti ti-scale text-xs text-accent" />
                  </div>
                  <span className="text-[12px] font-semibold text-text-3">BD Legal RAG</span>

                  {/* Status badges */}
                  <div className="ml-auto flex items-center gap-1.5">
                    {result.declined && (
                      <Badge variant="destructive">
                        <i className="ti ti-ban text-[10px] mr-1" />
                        Declined
                      </Badge>
                    )}
                    {result.degraded && (
                      <Badge variant="warning">
                        <i className="ti ti-alert-triangle text-[10px] mr-1" />
                        Degraded
                      </Badge>
                    )}
                    {result.cached && (
                      <Badge variant="secondary">
                        <i className="ti ti-bolt text-[10px] mr-1" />
                        Cached
                      </Badge>
                    )}
                  </div>
                </div>

                {result.declined ? (
                  <div className="flex items-start gap-3 py-2">
                    <i className="ti ti-scale-off text-lg text-score-red mt-0.5" />
                    <p className="text-sm text-text-2 leading-relaxed">{s.declined}</p>
                  </div>
                ) : (
                  <Markdown className="text-sm text-text-1 leading-relaxed">
                    {result.answer}
                  </Markdown>
                )}
              </div>

              {/* Disclaimer */}
              {result.disclaimer && (
                <div className="rounded-[10px] border border-score-amber-border bg-score-amber-bg p-4">
                  <div className="flex items-start gap-2.5">
                    <i className="ti ti-info-circle text-score-amber text-base mt-0.5 shrink-0" />
                    <div>
                      <p className="text-[12px] font-semibold text-score-amber mb-1">
                        {s.disclaimer_label}
                      </p>
                      <p className="text-[12px] text-text-2 leading-relaxed">
                        {result.disclaimer}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-border bg-surface p-4">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={(e) => void handleSubmit(e)}>
            <div className="border border-border rounded-[10px] bg-page focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all overflow-hidden">
              <Textarea
                ref={textareaRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
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
                  className="h-7 text-xs w-44 bg-surface"
                >
                  <option value="">All Acts</option>
                  {actsQ.data?.map((a) => (
                    <option key={a.slug} value={a.slug}>
                      {a.short_name}
                    </option>
                  ))}
                </Select>
                <span className="text-[11px] text-text-4 ml-1">
                  ⌘↵ to send
                </span>
                <div className="ml-auto">
                  <Button
                    type="submit"
                    disabled={streaming || !question.trim()}
                    size="sm"
                    className="gap-1.5"
                  >
                    {streaming ? (
                      <>
                        <i className="ti ti-loader-2 animate-spin text-sm" />
                        {s.sending}
                      </>
                    ) : (
                      <>
                        <i className="ti ti-send text-sm" />
                        {s.send}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
