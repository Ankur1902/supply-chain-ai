import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 p-12 text-center">
      <AlertTriangle className="h-8 w-8 text-destructive" />
      <p className="text-sm text-muted-foreground">
        {message ?? "Something went wrong loading this data."}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}
