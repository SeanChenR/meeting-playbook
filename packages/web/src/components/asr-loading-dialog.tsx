/**
 * AsrLoadingDialog — non-dismissible modal shown while session.phase === "connecting".
 *
 * Hooks into the existing meeting-session WebSocket lifecycle: when the user
 * clicks 開始 and the Qwen ASR model is lazy-loaded by the backend (~30s first
 * time, ~2s cached), this dialog renders so the user has feedback instead of
 * staring at a dead button. Auto-dismisses when phase leaves "connecting".
 *
 * Uses a custom inline bar visualiser (24 framer-motion bars with randomised
 * height oscillation) — visually equivalent to the ElevenLabs BarVisualizer
 * but without the external dependency.
 *
 * The project's <Dialog> auto-dismisses on Escape / backdrop click via
 * `onOpenChange(false)`. To make this dialog non-dismissible we pass an
 * `onOpenChange` that simply ignores `false` requests — only a phase change
 * (open prop flipping to false) can close it.
 */

import { motion, useReducedMotion } from "motion/react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";

export type AsrSessionPhase = "idle" | "connecting" | "in_progress" | "ending" | "ended" | "error";

export interface AsrLoadingDialogProps {
  phase: AsrSessionPhase;
}

const _BAR_COUNT = 24;

function _BarVisualizer() {
  const reduced = useReducedMotion();
  const bars = useMemo(
    () =>
      Array.from({ length: _BAR_COUNT }, (_, i) => ({
        offset: i * 0.08,
        amp: 0.45 + ((i * 13) % 11) / 22,
      })),
    [],
  );

  return (
    <div
      data-testid="bar-visualizer"
      className="flex h-16 items-end justify-center gap-1"
      aria-hidden
    >
      {bars.map((b, i) => (
        <motion.span
          key={i}
          className="block h-12 w-1.5 rounded-full bg-(--color-primary)"
          style={{ originY: 1 }}
          initial={{ scaleY: 0.3 }}
          animate={
            reduced
              ? { scaleY: 0.55 }
              : {
                  scaleY: [0.25, b.amp, 0.35, b.amp * 0.8, 0.25],
                }
          }
          transition={
            reduced
              ? { duration: 0 }
              : {
                  duration: 1.2,
                  repeat: Infinity,
                  ease: "easeInOut",
                  delay: b.offset,
                }
          }
        />
      ))}
    </div>
  );
}

export function AsrLoadingDialog({ phase }: AsrLoadingDialogProps) {
  const { t } = useTranslation();
  const open = phase === "connecting";

  return (
    <Dialog
      open={open}
      onOpenChange={() => {
        // Intentionally a no-op: only phase change (open prop flip) closes
        // this dialog. Escape / backdrop click are absorbed.
      }}
    >
      <DialogContent
        data-testid="asr-loading-dialog"
        className="max-w-md gap-6 bg-(--color-primary-soft)/40 backdrop-blur"
      >
        <_BarVisualizer />
        <DialogHeader className="text-center">
          <DialogTitle className="text-center text-lg font-semibold">
            {t("meetings.session.asrLoading.title")}
          </DialogTitle>
          <DialogDescription className="text-center text-sm leading-snug">
            {t("meetings.session.asrLoading.subtitle")}
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  );
}
