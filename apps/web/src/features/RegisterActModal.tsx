import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface RegisterActModalProps {
  open: boolean;
  onClose: () => void;
}

export function RegisterActModal({ open, onClose }: RegisterActModalProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Register a new Act">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground leading-relaxed">
          Acts are registered declaratively by adding a YAML file to the repository and
          running the bootstrap command. This console manages ingestion only.
        </p>

        <div className="rounded-lg bg-muted/50 border border-border p-3 space-y-3">
          {[
            {
              step: "1",
              icon: "ti-file-type-yml",
              label: "Add YAML file",
              code: "config/acts/<slug>.yaml",
            },
            {
              step: "2",
              icon: "ti-terminal",
              label: "Run bootstrap",
              code: "python -m app.ingestion.registry bootstrap",
            },
            {
              step: "3",
              icon: "ti-refresh",
              label: "Ingest",
              desc: "Use the Ingest button to crawl and index the Act.",
            },
          ].map(({ step, icon, label, code, desc }) => (
            <div key={step} className="flex items-start gap-2.5">
              <span className="w-5 h-5 rounded-md bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                <i className={`ti ${icon} text-[11px] text-primary`} />
              </span>
              <div>
                <div className="text-xs font-semibold text-foreground">{step}. {label}</div>
                {code && (
                  <code className="text-[11px] text-muted-foreground bg-background px-1.5 py-0.5 rounded border border-border font-mono">
                    {code}
                  </code>
                )}
                {desc && <span className="text-[11px] text-muted-foreground">{desc}</span>}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-1">
          <Button variant="secondary" onClick={onClose}>Close</Button>
        </div>
      </div>
    </Dialog>
  );
}
