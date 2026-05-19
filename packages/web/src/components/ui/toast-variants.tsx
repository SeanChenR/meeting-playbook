/**
 * Toast semantic variants — ui-overhaul-primitive-upgrade task 8.
 *
 * JSX-friendly aliases over the underlying `toast.info/.success/.warning/.error`
 * helpers exposed by `./sonner`. Stripe colour comes from `[data-type=...]`
 * selectors on `<Toaster />`.
 */

import type { ExternalToast } from "sonner";

import { toast } from "./sonner";

export type ToastVariant = "info" | "success" | "warning" | "error";

export interface SemanticToastOptions {
  description?: string;
  duration?: number;
  action?: { label: string; onClick: () => void };
}

function _coerce(options?: SemanticToastOptions): ExternalToast | undefined {
  if (!options) return undefined;
  const next: ExternalToast = {};
  if (options.description !== undefined) next.description = options.description;
  if (options.duration !== undefined) next.duration = options.duration;
  if (options.action) {
    next.action = { label: options.action.label, onClick: options.action.onClick };
  }
  return next;
}

export function ToastInfo(message: string, options?: SemanticToastOptions): string | number {
  return toast.info(message, _coerce(options));
}

export function ToastSuccess(message: string, options?: SemanticToastOptions): string | number {
  return toast.success(message, _coerce(options));
}

export function ToastWarning(message: string, options?: SemanticToastOptions): string | number {
  return toast.warning(message, _coerce(options));
}

export function ToastError(message: string, options?: SemanticToastOptions): string | number {
  return toast.error(message, _coerce(options));
}
