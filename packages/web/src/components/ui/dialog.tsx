/**
 * Dialog — animate-ui motion + Aura surface tokens (ui-overhaul-primitive-upgrade task 2).
 *
 * Shadcn-shape API preserved:
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
 * Motion: backdrop fade + 8px blur; content scale 0.96 -> 1 + fade.
 * Respects prefers-reduced-motion via motion/react's useReducedMotion
 * (returns instant variants).
 *
 * Source motif: https://animate-ui.com/docs/components/base/dialog (CC0).
 */

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
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

  return (
    <_DialogContext.Provider value={ctxValue}>
      <AnimatePresence>{open ? children : null}</AnimatePresence>
    </_DialogContext.Provider>
  );
}

export interface DialogContentProps {
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}

export function DialogContent({
  children,
  className,
  "data-testid": dataTestId,
}: DialogContentProps) {
  const { onOpenChange, titleId, descriptionId } = _useDialogContext();
  const prefersReducedMotion = useReducedMotion();

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onOpenChange(false);
      }
    },
    [onOpenChange],
  );

  const backdropVariants = prefersReducedMotion
    ? { hidden: { opacity: 1 }, visible: { opacity: 1 } }
    : { hidden: { opacity: 0 }, visible: { opacity: 1 } };

  const contentVariants = prefersReducedMotion
    ? { hidden: { opacity: 1, scale: 1 }, visible: { opacity: 1, scale: 1 } }
    : {
        hidden: { opacity: 0, scale: 0.96 },
        visible: { opacity: 1, scale: 1 },
      };

  // Portal to <body> so the backdrop escapes any ancestor stacking context
  // (e.g. `transform`, `filter`, or `overflow-hidden` containers — the
  // ShineBorder bars now create one, which clipped the dialog backdrop and
  // let the sticky mini-player show through behind the haze).
  const portalTarget = _usePortalTarget();
  if (!portalTarget) return null;

  return createPortal(
    <motion.div
      role="presentation"
      onClick={handleBackdropClick}
      initial="hidden"
      animate="visible"
      exit="hidden"
      variants={backdropVariants}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        data-testid={dataTestId}
        initial="hidden"
        animate="visible"
        exit="hidden"
        variants={contentVariants}
        transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "w-full max-w-md rounded-(--radius-lg) border border-(--color-border) bg-(--color-surface) p-6 shadow-(--shadow-lg)",
          className,
        )}
      >
        {children}
      </motion.div>
    </motion.div>,
    portalTarget,
  );
}

/** Defers the portal mount until after first render so SSR-style tests
 *  (happy-dom) don't trip over `document.body` being undefined at module
 *  evaluation time. */
function _usePortalTarget(): HTMLElement | null {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setTarget(document.body);
  }, []);
  return target;
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
