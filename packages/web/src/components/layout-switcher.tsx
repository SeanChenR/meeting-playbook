/**
 * LayoutSwitcher — slice ui-overhaul-claude-design task 5.4.
 *
 * Icon-only segmented control matching the design bundle: a single bordered
 * "pill" with 3px outer padding wrapping two 26px-tall icon buttons. Active
 * state uses `--color-muted` background + `--color-foreground` text; inactive
 * fades to `--color-muted-foreground`.
 *
 * `stack`  → Rows icon  (vertical strips)
 * `columns`→ Cols icon (horizontal strips)
 *
 * Default value is read from `localStorage.mp-detail-layout` on mount so a
 * fresh remount honours the user's last choice. Persistence is handled by
 * the parent's `onChange` (existing `useDetailLayout` already writes there).
 */

import { Columns3, Rows3 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { DetailLayout } from "../hooks/use-detail-layout";
import { cn } from "../lib/utils";

export interface LayoutSwitcherProps {
  layout: DetailLayout;
  onChange: (next: DetailLayout) => void;
}

export function LayoutSwitcher({ layout, onChange }: LayoutSwitcherProps) {
  const { t } = useTranslation();

  function _btnCls(active: boolean): string {
    return cn(
      "inline-flex h-[26px] items-center justify-center rounded-[5px] px-2 transition-colors",
      active
        ? "bg-(--color-muted) text-(--color-foreground)"
        : "text-(--color-muted-foreground) hover:text-(--color-foreground)",
    );
  }

  return (
    <div
      data-testid="layout-switcher"
      role="group"
      aria-label={t("meetings.detail.layout.columns")}
      className="inline-flex items-center gap-0.5 rounded-md border border-(--color-border) bg-(--color-card) p-[3px]"
    >
      <button
        type="button"
        data-testid="layout-switcher-columns"
        aria-label={t("meetings.detail.layout.columns")}
        aria-pressed={layout === "columns"}
        title={t("meetings.detail.layout.columns")}
        onClick={() => onChange("columns")}
        className={_btnCls(layout === "columns")}
      >
        <Columns3 className="size-[15px]" />
      </button>
      <button
        type="button"
        data-testid="layout-switcher-stack"
        aria-label={t("meetings.detail.layout.stack")}
        aria-pressed={layout === "stack"}
        title={t("meetings.detail.layout.stack")}
        onClick={() => onChange("stack")}
        className={_btnCls(layout === "stack")}
      >
        <Rows3 className="size-[15px]" />
      </button>
    </div>
  );
}
