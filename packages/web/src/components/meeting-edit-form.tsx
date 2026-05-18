/**
 * Inline edit form for meeting metadata — slice-15 task 4.1.
 *
 * Owns the 5 mutable fields exposed by the PATCH endpoint: title,
 * scheduled_start_at, scheduled_end_at, counterparty_display_name,
 * me_display_name. (asr_provider has its own selector already.)
 *
 * Submit invokes `patchMeeting`, invalidates the cached meeting + list
 * queries, calls `onSaved`, and surfaces a localized error on the 422
 * envelope. The component stays a controlled `<form>` driven by
 * react-hook-form + zod; the calling route decides where to mount it.
 */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { localizedErrorMessage } from "@/lib/i18n-errors";
import { type MeetingDetail, type MeetingPatchPayload, patchMeeting } from "@/lib/meetings-api";

export interface MeetingEditFormProps {
  meeting: MeetingDetail;
  onSaved: (updated: MeetingDetail) => void;
  onCancel?: () => void;
}

// Zod schema mirrors the backend MeetingPatch contract — every field
// is optional but non-empty when present; end >= start cross-field.
const _editSchema = z
  .object({
    title: z.string().min(1).max(200),
    scheduled_start_at: z.string().min(1),
    scheduled_end_at: z.string().optional(),
    counterparty_display_name: z.string().min(1).max(100),
    me_display_name: z.string().min(1).max(100),
  })
  .refine(
    (data) =>
      !data.scheduled_end_at ||
      new Date(data.scheduled_end_at).getTime() >= new Date(data.scheduled_start_at).getTime(),
    {
      path: ["scheduled_end_at"],
      message: "errors.meeting.invalid_time_range",
    },
  );

type EditFormValues = z.infer<typeof _editSchema>;

function _toDatetimeLocal(value: string | null | undefined): string {
  // `datetime-local` wants `yyyy-MM-ddTHH:mm` (no timezone). The backend
  // stores UTC; the input must show the user's LOCAL equivalent.
  //
  // Slice-16 polish bugfix: the previous implementation `.slice(0, 16)`
  // stripped the `Z` and showed UTC time as if it were local — so a
  // meeting recorded at 18:34 UTC showed as 18:34 local (off by the
  // user's TZ offset), and saving without editing would re-interpret
  // the UTC string AS local → silent 8-hour shift on every save round
  // trip in GMT+8.
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function _toIso(value: string): string | undefined {
  // `datetime-local` value comes back without a timezone; assume the
  // user typed local time and serialise as UTC (matching what the
  // backend stores). `new Date(localString)` already interprets the
  // string as local time, so `.toISOString()` produces the correct UTC.
  if (!value) return undefined;
  return new Date(value).toISOString();
}

export function MeetingEditForm({ meeting, onSaved, onCancel }: MeetingEditFormProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const form = useForm<EditFormValues>({
    resolver: zodResolver(_editSchema),
    defaultValues: {
      title: meeting.title,
      scheduled_start_at: _toDatetimeLocal(meeting.scheduled_start_at),
      scheduled_end_at: _toDatetimeLocal(meeting.scheduled_end_at),
      counterparty_display_name: meeting.counterparty_display_name,
      me_display_name: meeting.me_display_name,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    setSavedFlash(false);

    // Build a sparse PATCH body — only include fields the user actually
    // touched (react-hook-form's dirtyFields tracks input.onChange events
    // rather than value-equality, sidestepping ISO-string normalisation
    // drift on the datetime-local inputs).
    const dirty = form.formState.dirtyFields;
    const payload: MeetingPatchPayload = {};
    if (dirty.title) {
      payload.title = values.title;
    }
    if (dirty.scheduled_start_at) {
      const desiredStart = _toIso(values.scheduled_start_at);
      if (desiredStart) payload.scheduled_start_at = desiredStart;
    }
    if (dirty.scheduled_end_at) {
      const desiredEnd = _toIso(values.scheduled_end_at || "");
      payload.scheduled_end_at = desiredEnd ?? null;
    }
    if (dirty.counterparty_display_name) {
      payload.counterparty_display_name = values.counterparty_display_name;
    }
    if (dirty.me_display_name) {
      payload.me_display_name = values.me_display_name;
    }

    try {
      const updated = await patchMeeting(meeting.id, payload);
      queryClient.invalidateQueries({ queryKey: ["meeting", meeting.id] });
      queryClient.invalidateQueries({ queryKey: ["meetings"] });
      onSaved(updated);
      setSavedFlash(true);
    } catch (err) {
      const code =
        err && typeof err === "object" && "errorCode" in err
          ? String((err as { errorCode: string }).errorCode)
          : "errors.common.unknown";
      setServerError(localizedErrorMessage(code, t));
    }
  });

  // Map zod refinement key "errors.meeting.invalid_time_range" → localized.
  const endError = form.formState.errors.scheduled_end_at?.message;
  const endErrorLocalized = endError
    ? localizedErrorMessage(endError.replace("errors.", ""), t)
    : null;

  return (
    <form data-testid="meeting-edit-form" onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="meeting-edit-title">{t("meetings.edit.title")}</Label>
        <Input id="meeting-edit-title" type="text" {...form.register("title")} />
        {form.formState.errors.title ? (
          <p className="text-xs text-(--color-destructive)">
            {localizedErrorMessage("meeting.title.required", t)}
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="meeting-edit-start">{t("meetings.edit.scheduledStart")}</Label>
          <Controller
            control={form.control}
            name="scheduled_start_at"
            render={({ field }) => (
              <DateTimePicker
                id="meeting-edit-start"
                value={field.value ?? ""}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="meeting-edit-end">{t("meetings.edit.scheduledEnd")}</Label>
          <Controller
            control={form.control}
            name="scheduled_end_at"
            render={({ field }) => (
              <DateTimePicker
                id="meeting-edit-end"
                value={field.value ?? ""}
                onChange={field.onChange}
                onBlur={field.onBlur}
              />
            )}
          />
          {endErrorLocalized ? (
            <p role="alert" className="text-xs text-(--color-destructive)">
              {endErrorLocalized}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="meeting-edit-counterparty">
            {t("meetings.edit.counterpartyDisplayName")}
          </Label>
          <Input
            id="meeting-edit-counterparty"
            type="text"
            {...form.register("counterparty_display_name")}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="meeting-edit-me">{t("meetings.edit.meDisplayName")}</Label>
          <Input id="meeting-edit-me" type="text" {...form.register("me_display_name")} />
        </div>
      </div>

      {serverError ? (
        <div
          role="alert"
          className="rounded-md border border-(--color-destructive)/30 bg-(--color-destructive)/10 px-3 py-2 text-sm text-(--color-destructive)"
        >
          {serverError}
        </div>
      ) : null}
      {savedFlash ? (
        <p data-testid="meeting-edit-saved-flash" className="text-sm text-(--color-success)">
          {t("meetings.edit.saved")}
        </p>
      ) : null}

      <footer className="flex justify-end gap-2">
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t("meetings.edit.cancel")}
          </Button>
        ) : null}
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? t("meetings.edit.saving") : t("meetings.edit.save")}
        </Button>
      </footer>
    </form>
  );
}
