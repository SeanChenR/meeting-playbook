/**
 * DateTimePicker — ui-overhaul-primitive-upgrade task 9 (Decision 5).
 *
 * Composes:
 *   - `<Calendar>` (Aura date grid, shadcnblocks calendar-standard-3 pattern)
 *   - `<Input type="time">` for HH:mm
 *
 * Value contract: emits / accepts a `yyyy-MM-ddTHH:mm` LOCAL string,
 * matching the legacy `<input type="datetime-local">` form schema so
 * forms don't need to rewrite their zod resolvers. Backend payload
 * shape (ISO datetime via `_toIso`) is untouched.
 */

import { CalendarIcon } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";
import { Calendar } from "./calendar";
import { Input } from "./input";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

export interface DateTimePickerProps {
  /** `yyyy-MM-ddTHH:mm` local string (matches `<input type="datetime-local">`). */
  value: string;
  onChange: (next: string) => void;
  onBlur?: () => void;
  id?: string;
  className?: string;
  "aria-labelledby"?: string;
}

function _parseLocal(value: string): { date: Date | undefined; time: string } {
  if (!value) return { date: undefined, time: "" };
  const [datePart, timePart = ""] = value.split("T");
  if (!datePart) return { date: undefined, time: "" };
  const [y, m, d] = datePart.split("-").map((n) => Number.parseInt(n, 10));
  if (!y || !m || !d) return { date: undefined, time: timePart };
  return { date: new Date(y, m - 1, d), time: timePart };
}

function _formatDateLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function _combine(date: Date | undefined, time: string, fallbackDate?: Date): string {
  const effective = date ?? fallbackDate;
  if (!effective) return "";
  return `${_formatDateLocal(effective)}T${time || "00:00"}`;
}

export function DateTimePicker({
  value,
  onChange,
  onBlur,
  id,
  className,
  "aria-labelledby": ariaLabelledBy,
}: DateTimePickerProps) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const reactId = useId();
  const fieldId = id ?? `dtp-${reactId}`;

  const { date, time } = useMemo(() => _parseLocal(value), [value]);

  const dateLabel = useMemo(() => {
    if (!date) return t("ui.calendar.openPicker");
    return new Intl.DateTimeFormat(i18n.language || "default", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date);
  }, [date, i18n.language, t]);

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      id={fieldId}
      aria-labelledby={ariaLabelledBy}
    >
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={t("ui.calendar.openPicker")}
            data-testid={`${fieldId}-date`}
            onBlur={onBlur}
            className="inline-flex h-9 flex-1 items-center justify-between gap-2 rounded-(--radius-md) border border-(--color-border) bg-(--color-surface) px-3 text-sm hover:border-(--color-primary)/40"
          >
            <span className={cn(!date && "text-(--color-muted-foreground)")}>{dateLabel}</span>
            <CalendarIcon className="size-4 text-(--color-muted-foreground)" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="p-0">
          <Calendar
            value={date}
            onChange={(next) => {
              onChange(_combine(next, time));
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      <Input
        type="time"
        data-testid={`${fieldId}-time`}
        aria-label={t("ui.calendar.openPicker")}
        value={time}
        onBlur={onBlur}
        onChange={(e) => onChange(_combine(date, e.target.value, new Date()))}
        className="w-28"
      />
    </div>
  );
}
