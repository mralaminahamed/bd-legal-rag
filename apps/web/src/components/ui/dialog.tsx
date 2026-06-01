import { type ReactNode, useEffect, useRef } from "react";
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

  useEffect(() => {
    if (open) ref.current?.showModal();
    else ref.current?.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className={cn(
        "rounded-lg border border-border bg-card p-6 shadow-xl backdrop:bg-black/50 w-full max-w-md",
        className
      )}
    >
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      {children}
    </dialog>
  );
}
