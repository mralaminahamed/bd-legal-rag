import { type ReactNode, useEffect, useRef, useId } from "react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}

export function Dialog({ open, onClose, title, children, className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open) {
      if (!el.open) el.showModal();
      // Prevent body scroll while modal is open
      document.body.style.overflow = "hidden";
    } else {
      if (el.open) el.close();
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // Close on backdrop click (click lands on <dialog> itself, not its children)
  function handleClick(e: React.MouseEvent<HTMLDialogElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={handleClick}
      aria-labelledby={titleId}
      className={cn(
        // Tailwind preflight zeroes out `margin: auto` — restore it for centering
        "m-auto",
        // Panel styles
        "w-full max-w-md rounded-xl bg-card text-card-foreground p-6",
        "shadow-2xl ring-1 ring-foreground/10",
        // Backdrop
        "backdrop:bg-black/60 backdrop:backdrop-blur-sm",
        // Entrance animation (tw-animate-css)
        "open:animate-in open:fade-in-0 open:zoom-in-95 open:duration-200",
        className,
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <h2 id={titleId} className="text-base font-semibold text-foreground leading-tight">{title}</h2>
        <button
          onClick={onClose}
          aria-label="Close"
          className="ml-4 shrink-0 -mt-0.5 -mr-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          <i className="ti ti-x text-sm" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
