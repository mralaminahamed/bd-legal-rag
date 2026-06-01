import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface RegisterActModalProps {
  open: boolean;
  onClose: () => void;
}

export function RegisterActModal({ open, onClose }: RegisterActModalProps) {
  return (
    <Dialog open={open} onClose={onClose} title="Register new Act">
      <p className="text-sm text-muted-foreground mb-4">
        New Acts are registered by adding a YAML file to{" "}
        <code className="bg-muted px-1 rounded text-xs">config/acts/</code> and
        running{" "}
        <code className="bg-muted px-1 rounded text-xs">
          python -m app.ingestion.registry bootstrap
        </code>
        . Once registered, use the Ingest button to crawl and index the Act.
      </p>
      <div className="flex justify-end">
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
      </div>
    </Dialog>
  );
}
