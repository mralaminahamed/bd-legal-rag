import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownProps {
  children: string;
  className?: string;
}

export function Markdown({ children, className }: MarkdownProps) {
  return (
    <div
      className={cn(
        "text-text-1 leading-relaxed",
        "[&_p]:mb-3 [&_p:last-child]:mb-0",
        "[&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_li]:mb-1",
        "[&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3",
        "[&_strong]:font-semibold [&_strong]:text-text-1",
        "[&_code]:bg-page [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-[12px] [&_code]:font-mono [&_code]:text-text-2 [&_code]:border [&_code]:border-border",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-accent/40 [&_blockquote]:pl-3 [&_blockquote]:text-text-3 [&_blockquote]:italic",
        "[&_h1]:text-[15px] [&_h1]:font-bold [&_h1]:mb-2",
        "[&_h2]:text-[14px] [&_h2]:font-bold [&_h2]:mb-2",
        "[&_h3]:text-[13px] [&_h3]:font-semibold [&_h3]:mb-1.5",
        className
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
