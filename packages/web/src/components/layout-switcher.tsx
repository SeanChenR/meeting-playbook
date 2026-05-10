/**
 * LayoutSwitcher — controlled toggle between Stack and Columns layouts.
 *
 * Slice-07. NO emojis. Uses inline SVG icons (lucide-style) so we don't
 * pull in another dependency just for two glyphs. The button currently
 * active gets `aria-pressed="true"` for screen readers.
 */

import { useTranslation } from "react-i18next";
import type { DetailLayout } from "../hooks/use-detail-layout";
import { cn } from "../lib/utils";

export interface LayoutSwitcherProps {
  layout: DetailLayout;
  onChange: (next: DetailLayout) => void;
}

function StackIcon() {
  return (
    <svg
      aria-hidden
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="2" y="2" width="12" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2" y="6.5" width="12" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="2" y="11" width="12" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function ColumnsIcon() {
  return (
    <svg
      aria-hidden
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="2" y="2" width="3" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="6.5" y="2" width="3" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="11" y="2" width="3" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function LayoutSwitcher({ layout, onChange }: LayoutSwitcherProps) {
  const { t } = useTranslation();

  function _btnCls(active: boolean): string {
    return cn(
      "inline-flex h-8 w-8 items-center justify-center rounded-md border border-(--color-border)",
      active
        ? "bg-(--color-primary) text-(--color-primary-foreground)"
        : "bg-(--color-card) text-(--color-muted-foreground) hover:bg-(--color-muted)",
    );
  }

  return (
    <div
      data-testid="layout-switcher"
      role="group"
      className="inline-flex items-center gap-1"
      aria-label={t("meetings.detail.layout.stack")}
    >
      <button
        type="button"
        data-testid="layout-switcher-stack"
        aria-label={t("meetings.detail.layout.stack")}
        aria-pressed={layout === "stack"}
        className={_btnCls(layout === "stack")}
        onClick={() => onChange("stack")}
      >
        <StackIcon />
      </button>
      <button
        type="button"
        data-testid="layout-switcher-columns"
        aria-label={t("meetings.detail.layout.columns")}
        aria-pressed={layout === "columns"}
        className={_btnCls(layout === "columns")}
        onClick={() => onChange("columns")}
      >
        <ColumnsIcon />
      </button>
    </div>
  );
}
