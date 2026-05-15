/**
 * SpeakerColorPopover — slice-16 task 6.3.
 *
 * Inline color-picker popover for a single `speaker_cluster_<N>` row.
 * The transcript pane mounts this when the user right-clicks a cluster
 * speaker name; `me` / `counterparty` / `speaker_cluster_unknown` are
 * filtered out by the caller (this component requires a numeric
 * `clusterN` prop, so the type system rejects mis-targeted opens).
 *
 * UX:
 *   1. Scheme picker — 5 radio chips, click to switch the global scheme
 *   2. Swatch grid — 6 hue/lightness swatches computed from the current
 *      scheme; clicking a swatch sets an override for this cluster
 *   3. Custom color input — `<input type="color">` for manual picks
 *   4. Reset button — clears the cluster's override (falls back to scheme)
 */

import { Palette } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useTranscriptColorPref } from "../hooks/use-transcript-color-pref";
import {
  TRANSCRIPT_COLOR_SCHEMES,
  TRANSCRIPT_COLOR_SCHEME_IDS,
  _resolveClusterColor,
  type SchemeId,
} from "../lib/transcript-color-schemes";

export interface SpeakerColorPopoverProps {
  /** 1-indexed cluster number. Caller MUST gate non-cluster speakers out. */
  clusterN: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** DOM element the popover should anchor to (positioning hint only). */
  anchorRef?: React.RefObject<HTMLElement | null>;
}

function _swatchPreview(scheme: SchemeId, hueIdx: number): { background: string; outline: string } {
  // Build a probe pref of the picker's currently-selected scheme so the
  // swatch preview matches what the resolver would render.
  const swatchColor = _resolveClusterColor(`speaker_cluster_${hueIdx + 1}`, {
    scheme,
    overrides: {},
  });
  return { background: swatchColor.accent, outline: swatchColor.accent };
}

function _hueForSwatch(scheme: SchemeId, hueIdx: number): number | null {
  // Slice-16 task 10.2: derive the hue stored as the override from the
  // active scheme's hue array. Grayscale has no hue → returns null and
  // the popover hides the swatch grid entirely.
  const hues = TRANSCRIPT_COLOR_SCHEMES[scheme].hues;
  const hue = hues[hueIdx % hues.length];
  return typeof hue === "number" ? hue : null;
}

export function SpeakerColorPopover({
  clusterN,
  open,
  onOpenChange,
  anchorRef,
}: SpeakerColorPopoverProps): ReactNode {
  const { t } = useTranslation();
  const { pref, setScheme, setOverride, resetOverride } = useTranscriptColorPref();
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onOpenChange(false);
    }
    function onClickOutside(e: MouseEvent) {
      if (!popoverRef.current) return;
      if (popoverRef.current.contains(e.target as Node)) return;
      if (anchorRef?.current && anchorRef.current.contains(e.target as Node)) return;
      onOpenChange(false);
    }
    document.addEventListener("keydown", onKeyDown);
    // Defer the click listener one frame so the same click that opened
    // the popover doesn't immediately close it.
    const timer = window.setTimeout(() => {
      document.addEventListener("mousedown", onClickOutside);
    }, 0);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onClickOutside);
      window.clearTimeout(timer);
    };
  }, [open, onOpenChange, anchorRef]);

  if (!open) return null;

  return (
    <div
      ref={popoverRef}
      role="dialog"
      aria-label={t("transcript.color.popoverTitle")}
      data-testid="speaker-color-popover"
      className="fixed z-50 w-72 rounded-lg border border-(--color-border) bg-(--color-card) p-4 shadow-lg"
      // Caller is expected to position via anchor; we default to a
      // sensible "near the top-left of viewport" position when used in
      // tests / programmatically without an anchor.
      style={
        anchorRef?.current
          ? _anchorPosition(anchorRef.current)
          : { top: "50%", left: "50%", transform: "translate(-50%, -50%)" }
      }
    >
      <header className="mb-3 flex items-center gap-2">
        <Palette className="size-4 text-(--color-muted-foreground)" aria-hidden />
        <h3 className="text-sm font-semibold text-(--color-foreground)">
          {t("transcript.color.popoverTitle")}
        </h3>
      </header>

      <section className="mb-3 space-y-1.5">
        <p className="text-xs text-(--color-muted-foreground)">
          {t("transcript.color.scheme.default") /* keep i18n usage */}
        </p>
        <div className="flex flex-wrap gap-1.5" data-testid="scheme-picker">
          {TRANSCRIPT_COLOR_SCHEME_IDS.map((id) => (
            <button
              key={id}
              type="button"
              data-testid={`scheme-chip-${id}`}
              data-active={pref.scheme === id}
              onClick={() => setScheme(id)}
              className={
                pref.scheme === id
                  ? "rounded-md border border-(--color-primary) bg-(--color-primary)/10 px-2 py-1 text-xs font-medium text-(--color-primary)"
                  : "rounded-md border border-(--color-border) px-2 py-1 text-xs text-(--color-muted-foreground) hover:text-(--color-foreground)"
              }
            >
              {t(`transcript.color.scheme.${_toLabelKey(id)}`)}
            </button>
          ))}
        </div>
      </section>

      {pref.scheme === "grayscale" ? (
        <section
          data-testid="swatch-grid-grayscale-hint"
          className="mb-3 rounded-md bg-(--color-muted)/40 px-3 py-2 text-xs text-(--color-muted-foreground)"
        >
          {t("transcript.color.grayscaleHint")}
        </section>
      ) : (
        <section className="mb-3 space-y-1.5">
          <p className="text-xs text-(--color-muted-foreground)">{t("transcript.color.swatch")}</p>
          <div className="grid grid-cols-6 gap-1.5" data-testid={`swatch-grid-${pref.scheme}`}>
            {Array.from({ length: 6 }).map((_, idx) => {
              const { background } = _swatchPreview(pref.scheme, idx);
              const hue = _hueForSwatch(pref.scheme, idx);
              return (
                <button
                  key={idx}
                  type="button"
                  data-testid={`color-swatch-${idx + 1}`}
                  onClick={() => hue !== null && setOverride(clusterN, hue)}
                  disabled={hue === null}
                  aria-label={`Swatch ${idx + 1}`}
                  style={{ background }}
                  className="size-7 rounded-md border border-(--color-border) transition-transform hover:scale-110 disabled:opacity-40"
                />
              );
            })}
          </div>
        </section>
      )}

      <footer className="flex justify-end">
        <button
          type="button"
          data-testid="reset-override"
          onClick={() => resetOverride(clusterN)}
          className="rounded-md border border-(--color-border) px-3 py-1.5 text-xs text-(--color-muted-foreground) hover:text-(--color-foreground)"
        >
          {t("transcript.color.resetToScheme")}
        </button>
      </footer>
    </div>
  );
}

function _toLabelKey(id: SchemeId): string {
  // i18n keys are camelCase; "high-contrast" → "highContrast".
  if (id === "high-contrast") return "highContrast";
  return id;
}

function _anchorPosition(anchor: HTMLElement): { top: number; left: number } {
  const rect = anchor.getBoundingClientRect();
  return { top: rect.bottom + 4, left: rect.left };
}

// Re-export for tests/consumers that want to introspect scheme metadata.
export { TRANSCRIPT_COLOR_SCHEMES };
