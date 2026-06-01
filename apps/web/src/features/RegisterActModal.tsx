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
        <p className="text-[13px] text-text-3 leading-relaxed">
          Acts are registered declaratively by adding a YAML file to the repository and
          running the bootstrap command. This console manages ingestion only.
        </p>

        <div className="rounded-lg bg-page border border-border p-3 space-y-2.5">
          <div className="flex items-start gap-2">
            <span className="w-5 h-5 rounded-md bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
              <i className="ti ti-file-type-yml text-[11px] text-accent" />
            </span>
            <div>
              <div className="text-[12px] font-semibold text-text-2">1. Add YAML</div>
              <code className="text-[11px] text-text-3 bg-surface px-1.5 py-0.5 rounded border border-border">
                config/acts/&lt;slug&gt;.yaml
              </code>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <span className="w-5 h-5 rounded-md bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
              <i className="ti ti-terminal text-[11px] text-accent" />
            </span>
            <div>
              <div className="text-[12px] font-semibold text-text-2">2. Bootstrap</div>
              <code className="text-[11px] text-text-3 bg-surface px-1.5 py-0.5 rounded border border-border">
                python -m app.ingestion.registry bootstrap
              </code>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <span className="w-5 h-5 rounded-md bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
              <i className="ti ti-refresh text-[11px] text-accent" />
            </span>
            <div>
              <div className="text-[12px] font-semibold text-text-2">3. Ingest</div>
              <span className="text-[11px] text-text-4">
                Use the Ingest button on this page to crawl and index the Act.
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-1">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
