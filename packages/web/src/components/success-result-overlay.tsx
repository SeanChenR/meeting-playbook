/**
 * SuccessResultOverlay — hazeover modal shown after upload / export completes.
 *
 * Centred card with check-mark animation, title, subtitle, optional primary
 * button. Backdrop is fixed-position, blurred, dim ("hazeover" style). Auto-
 * dismisses after `autoDismissMs` (default 3000), or via ESC / backdrop click.
 */

import { CircleCheck } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { cn } from "../lib/utils";

export interface SuccessResultOverlayProps {
  open: boolean;
  title: string;
  subtitle?: string;
  /** Milliseconds before auto-dismiss. 0 disables. Default 3000. */
  autoDismissMs?: number;
  onClose: () => void;
  primaryAction?: { label: string; onClick: () => void };
}

export function SuccessResultOverlay({
  open,
  title,
  subtitle,
  autoDismissMs = 3000,
  onClose,
  primaryAction,
}: SuccessResultOverlayProps) {
  const reduced = useReducedMotion();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open || !autoDismissMs || autoDismissMs <= 0) return;
    const t = setTimeout(() => closeRef.current(), autoDismissMs);
    return () => clearTimeout(t);
  }, [open, autoDismissMs]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeRef.current();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="overlay"
          data-testid="success-result-overlay"
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className={cn(
            "fixed inset-0 z-[60] flex items-center justify-center",
            "bg-black/30 backdrop-blur-sm",
          )}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={reduced ? { duration: 0 } : { duration: 0.18 }}
          onClick={(e) => {
            // Backdrop click (target === currentTarget): dismiss
            if (e.target === e.currentTarget) closeRef.current();
          }}
        >
          <motion.div
            data-testid="success-result-card"
            className={cn(
              "flex w-full max-w-sm flex-col items-center gap-3 rounded-xl px-8 py-7",
              "bg-(--color-surface) shadow-2xl border border-(--color-border)",
            )}
            initial={{ scale: 0.92, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
          >
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={
                reduced
                  ? { duration: 0 }
                  : { delay: 0.08, type: "spring", stiffness: 400, damping: 22 }
              }
              className="flex size-14 items-center justify-center rounded-full bg-(--color-success)/15 text-(--color-success)"
            >
              <CircleCheck size={32} strokeWidth={1.8} />
            </motion.div>
            <div className="space-y-0.5 text-center">
              <p className="text-base font-semibold text-(--color-foreground)">{title}</p>
              {subtitle && <p className="text-sm text-(--color-muted-foreground)">{subtitle}</p>}
            </div>
            {primaryAction && (
              <button
                type="button"
                onClick={() => {
                  primaryAction.onClick();
                  closeRef.current();
                }}
                className={cn(
                  "mt-2 inline-flex items-center justify-center rounded-md px-4 py-1.5 text-sm font-medium",
                  "bg-(--color-primary) text-(--color-primary-foreground) hover:bg-(--color-primary-hover)",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring) focus-visible:ring-offset-2",
                )}
              >
                {primaryAction.label}
              </button>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
