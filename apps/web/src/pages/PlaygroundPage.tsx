import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getActs } from "@/api/query";
import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Markdown } from "@/components/ui/markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { API_BASE_URL } from "@/lib/config";
import type { StreamEvent } from "@/types/api";
import { Send } from "lucide-react";

const UI_STRINGS = {
  en: {
    placeholder: "Ask a legal question in Bengali or English…",
    send: "Ask",
    sending: "Thinking…",
    disclaimer_label: "Legal Disclaimer",
    declined: "This question cannot be answered — please consult a qualified lawyer.",
    degraded: "Answer generated in degraded mode (provisions only, no summary).",
    cached: "Served from cache.",
  },
  bn: {
    placeholder: "বাংলা বা ইংরেজিতে আইনি প্রশ্ন জিজ্ঞাসা করুন…",
    send: "জিজ্ঞাসা করুন",
    sending: "চিন্তা করছি…",
    disclaimer_label: "আইনি দায়মুক্তি",
    declined: "এই প্রশ্নের উত্তর দেওয়া সম্ভব নয় — একজন যোগ্য আইনজীবীর পরামর্শ নিন।",
    degraded: "অবনত মোডে উত্তর তৈরি হয়েছে।",
    cached: "ক্যাশ থেকে পরিবেশিত।",
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

  const actsQ = useQuery({
    queryKey: ["acts"],
    queryFn: getActs,
    staleTime: Infinity,
  });

  const s = UI_STRINGS[uiLang];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;

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

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Playground"
        description="Bilingual legal Q&A — powered by bd-legal-rag"
        action={
          <Select
            value={uiLang}
            onChange={(e) => setUiLang(e.target.value as UILang)}
            className="w-32"
          >
            <option value="en">English UI</option>
            <option value="bn">বাংলা UI</option>
          </Select>
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={s.placeholder}
            rows={3}
            disabled={streaming}
            className="resize-none"
          />
          <div className="flex items-center gap-3">
            <div className="w-56">
              <Select
                value={actSlug}
                onChange={(e) => setActSlug(e.target.value)}
                disabled={streaming}
              >
                <option value="">All Acts</option>
                {actsQ.data?.map((a) => (
                  <option key={a.slug} value={a.slug}>
                    {a.short_name}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={streaming || !question.trim()}>
              <Send className="h-4 w-4" />
              {streaming ? s.sending : s.send}
            </Button>
          </div>
        </form>

        {/* Streaming in progress */}
        {streaming && streamText && (
          <Card>
            <CardContent className="pt-4">
              <div className="text-sm whitespace-pre-wrap">{streamText}</div>
              <div className="mt-2 flex gap-2">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-24" />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Final result */}
        {result && (
          <div className="space-y-3">
            <Card>
              <CardContent className="pt-4 space-y-3">
                <div className="flex items-center gap-2">
                  {result.declined && (
                    <Badge variant="destructive">Declined</Badge>
                  )}
                  {result.degraded && (
                    <Badge variant="warning">Degraded</Badge>
                  )}
                  {result.cached && (
                    <Badge variant="secondary">Cached</Badge>
                  )}
                </div>

                {result.declined ? (
                  <p className="text-sm text-muted-foreground">{s.declined}</p>
                ) : (
                  <Markdown>{result.answer}</Markdown>
                )}
              </CardContent>
            </Card>

            {result.disclaimer && (
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-900/50 dark:bg-yellow-900/20">
                <p className="text-xs font-medium text-yellow-800 dark:text-yellow-300 mb-1">
                  {s.disclaimer_label}
                </p>
                <p className="text-xs text-yellow-700 dark:text-yellow-400">
                  {result.disclaimer}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
