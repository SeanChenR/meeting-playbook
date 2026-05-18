/**
 * Calendar (date picker) — ui-overhaul-primitive-upgrade task 9.
 *
 * Aura-themed month grid. Pattern modelled on shadcnblocks
 * `calendar-standard-3` (free tier).
 * Source: https://www.shadcnblocks.com/component/calendar/calendar-standard-3
 *
 * Used by meeting create/edit forms; pairs with a separate `<Input type="time">`
 * to keep the form schema as an ISO datetime string.
 */

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";

export interface CalendarPickerProps {
  value?: Date;
  onChange: (next: Date) => void;
  min?: Date;
  max?: Date;
  className?: string;
}

function _startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function _addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

function _sameDay(a: Date | undefined, b: Date): boolean {
  if (!a) return false;
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function _isOutOfRange(d: Date, min?: Date, max?: Date): boolean {
  if (min && d < min) return true;
  if (max && d > max) return true;
  return false;
}

export function Calendar({ value, onChange, min, max, className }: CalendarPickerProps) {
  const { t, i18n } = useTranslation();
  const [cursor, setCursor] = useState<Date>(() => _startOfMonth(value ?? new Date()));
  const locale = i18n.language || "default";

  const monthLabel = useMemo(
    () => new Intl.DateTimeFormat(locale, { year: "numeric", month: "long" }).format(cursor),
    [cursor, locale],
  );

  const weekdayLabels = useMemo(() => {
    const fmt = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
    // Week starts Sunday (0..6).
    return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2024, 11, 1 + i)));
  }, [locale]);

  const days = useMemo(() => {
    const first = _startOfMonth(cursor);
    const startWeekday = first.getDay();
    const result: { date: Date; outside: boolean }[] = [];
    for (let i = 0; i < startWeekday; i += 1) {
      const d = new Date(first);
      d.setDate(d.getDate() - (startWeekday - i));
      result.push({ date: d, outside: true });
    }
    const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    for (let i = 1; i <= last; i += 1) {
      result.push({ date: new Date(cursor.getFullYear(), cursor.getMonth(), i), outside: false });
    }
    while (result.length % 7 !== 0) {
      const tailIdx = result.length - 1;
      const tail = result[tailIdx];
      if (!tail) break;
      const next = new Date(tail.date);
      next.setDate(next.getDate() + 1);
      result.push({ date: next, outside: true });
    }
    return result;
  }, [cursor]);

  const today = new Date();

  return (
    <div
      className={cn(
        "inline-block rounded-(--radius-md) border border-(--color-border) bg-(--color-surface) p-3 text-sm",
        className,
      )}
      data-testid="calendar"
    >
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label={t("ui.calendar.prevMonth")}
          data-testid="calendar-prev"
          onClick={() => setCursor(_addMonths(cursor, -1))}
          className="inline-flex size-7 items-center justify-center rounded-(--radius-sm) text-(--color-muted-foreground) hover:bg-(--color-surface-2)"
        >
          <ChevronLeft className="size-4" />
        </button>
        <div className="font-medium text-(--color-foreground)">{monthLabel}</div>
        <button
          type="button"
          aria-label={t("ui.calendar.nextMonth")}
          data-testid="calendar-next"
          onClick={() => setCursor(_addMonths(cursor, 1))}
          className="inline-flex size-7 items-center justify-center rounded-(--radius-sm) text-(--color-muted-foreground) hover:bg-(--color-surface-2)"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>
      <div className="mb-1 grid grid-cols-7 gap-1 text-center text-xs text-(--color-muted-foreground)">
        {weekdayLabels.map((w, i) => (
          <div key={`${w}-${i}`}>{w}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {days.map(({ date, outside }) => {
          const disabled = _isOutOfRange(date, min, max);
          const selected = _sameDay(value, date);
          const isToday = _sameDay(today, date);
          return (
            <button
              key={date.toISOString()}
              type="button"
              disabled={disabled}
              data-selected={selected || undefined}
              data-today={isToday || undefined}
              onClick={() => onChange(date)}
              className={cn(
                "inline-flex size-8 items-center justify-center rounded-(--radius-sm) text-sm",
                outside ? "text-(--color-subtle-foreground)" : "text-(--color-foreground)",
                "hover:bg-(--color-surface-2)",
                "disabled:cursor-not-allowed disabled:opacity-40",
                selected &&
                  "bg-(--color-primary) text-(--color-primary-foreground) hover:bg-(--color-primary)",
                !selected && isToday && "ring-1 ring-(--color-primary)",
              )}
            >
              {date.getDate()}
            </button>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs">
        <button
          type="button"
          onClick={() => onChange(new Date())}
          className="text-(--color-primary) hover:underline"
        >
          {t("ui.calendar.today")}
        </button>
      </div>
    </div>
  );
}
