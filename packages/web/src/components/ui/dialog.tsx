/**
 * Minimal Dialog — shadcn-shaped API (no Radix dep) used for inline
 * meeting edit modal (slice-15 task 8.1).
 *
 * Compositional pieces:
 *   <Dialog open onOpenChange>
 *     <DialogContent>
 *       <DialogHeader>
 *         <DialogTitle>...</DialogTitle>
 *         <DialogDescription>...</DialogDescription>
 *       </DialogHeader>
 *       {children}
 *     </DialogContent>
 *   </Dialog>
 *
 * Closes on Escape key + backdrop click. ARIA: role="dialog",
 * aria-modal="true", aria-labelledby auto-wires the title id.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  type ReactNode,
} from "react";
import { cn } from "../../lib/utils";

interface DialogContextValue {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  titleId: string;
  descriptionId: string;
}

const _DialogContext = createContext<DialogContextValue | null>(null);

function _useDialogContext(): DialogContextValue {
  const ctx = useContext(_DialogContext);
  if (!ctx) {
    throw new Error("Dialog subcomponents must be rendered inside <Dialog>");
  }
  return ctx;
}

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  const titleId = useId();
  const descriptionId = useId();

  const ctxValue = useMemo<DialogContextValue>(
    () => ({ open, onOpenChange, titleId, descriptionId }),
    [open, onOpenChange, titleId, descriptionId],
  );

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onOpenChange(false);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange]);

  if (!open) return null;

  return <_DialogContext.Provider value={ctxValue}>{children}</_DialogContext.Provider>;
}

export interface DialogContentProps {
  children: ReactNode;
  className?: string;
}

export function DialogContent({ children, className }: DialogContentProps) {
  const { onOpenChange, titleId, descriptionId } = _useDialogContext();

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onOpenChange(false);
      }
    },
    [onOpenChange],
  );

  return (
    <div
      role="presentation"
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          "w-full max-w-md rounded-lg border border-(--color-border) bg-(--color-card) p-6 shadow-lg",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}

export interface DialogHeaderProps {
  children: ReactNode;
  className?: string;
}

export function DialogHeader({ children, className }: DialogHeaderProps) {
  return <div className={cn("mb-4 space-y-1.5", className)}>{children}</div>;
}

export interface DialogTitleProps {
  children: ReactNode;
  className?: string;
}

export function DialogTitle({ children, className }: DialogTitleProps) {
  const { titleId } = _useDialogContext();
  return (
    <h2 id={titleId} className={cn("text-lg font-semibold text-(--color-foreground)", className)}>
      {children}
    </h2>
  );
}

export interface DialogDescriptionProps {
  children: ReactNode;
  className?: string;
}

export function DialogDescription({ children, className }: DialogDescriptionProps) {
  const { descriptionId } = _useDialogContext();
  return (
    <p id={descriptionId} className={cn("text-sm text-(--color-muted-foreground)", className)}>
      {children}
    </p>
  );
}
