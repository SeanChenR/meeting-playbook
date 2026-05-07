/**
 * Minimal AlertDialog — modal confirmation pattern (shadcn-shaped API).
 *
 * Hand-rolled with native React state (no Radix dep). Renders a backdrop
 * + centered card with title, description, and footer buttons. The dialog
 * traps focus on the confirm button when opened.
 */

import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./button";
import { cn } from "../../lib/utils";

export interface AlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel: ReactNode;
  cancelLabel: ReactNode;
  onConfirm: () => void;
  destructive?: boolean;
}

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  destructive = false,
}: AlertDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) confirmRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      className={cn("fixed inset-0 z-50 flex items-center justify-center", "bg-black/40 p-4")}
    >
      <div className="w-full max-w-md rounded-lg border border-(--color-border) bg-(--color-card) p-6 shadow-lg">
        <h2 className="text-lg font-semibold">{title}</h2>
        {description && (
          <p className="mt-2 text-sm text-(--color-muted-foreground)">{description}</p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            ref={confirmRef}
            variant={destructive ? "destructive" : "primary"}
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
