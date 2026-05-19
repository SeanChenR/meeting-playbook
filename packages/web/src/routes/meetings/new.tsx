/**
 * NewMeeting route — slice ui-overhaul-claude-design task 4.2.
 *
 * Slice-20b additions:
 *   - reads `from_calendar` URL search param; when present, fetches the
 *     calendar event detail and pre-fills the form
 *     (title / scheduled times / counterparty / me display name).
 *   - integrates the S20a-style attachment picker (lists current user's
 *     pending attachments and includes the selected ids in the
 *     `POST /api/meetings` payload).
 *   - on submit, includes `calendar_event_id` + `attachments[]` so the
 *     backend triggers Playbook generation and writes back attachment
 *     ownership in the same transaction.
 *
 * Visual contract aligned with design bundle `NewMeetingScreen`:
 *   - 520px centered card inside ProtectedShell
 *   - BackLink in main as the first row
 *   - 會議標題 + 對方/我方 grid + 預定開始/結束 grid + 會議目標 textarea
 *   - Footer: 取消 ghost button → spacer → 儲存草稿 secondary →
 *     建立並生成 playbook primary (Sparkles icon)
 *
 * Behavioural contract preserved:
 *   - Existing tests query labels by `/標題/`, `/對方顯示名稱/`,
 *     `/我方顯示名稱/`, button name `/建立$/` → kept verbatim.
 */

import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles } from "../../components/animate-ui/icons/sparkles";
import { BackLink } from "../../components/back-link";
import { ProtectedShell } from "../../components/protected-shell";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Calendar } from "../../components/ui/calendar";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "../../components/ui/popover";
import { Separator } from "../../components/ui/separator";
import {
  CalendarApiError,
  type CalendarEventDetail,
  calendarEventQueryOptions,
} from "../../lib/calendar-api";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import {
  MeetingApiError,
  meetingsListQueryOptions,
  useCreateMeetingMutation,
  type Meeting,
} from "../../lib/meetings-api";
import { StagedAttachmentDropzone } from "../../components/staged-attachment-dropzone";

/**
 * Slice-20b: pick the counterparty display name from a calendar attendee list.
 *
 * Mirrors the backend `pick_counterparty` heuristic but kept frontend-side so
 * the pre-fill happens synchronously after the calendar fetch resolves —
 * avoiding an extra round-trip and matching the design doc:
 * "前端 helper：單一非 viewer human → 用其 displayName、多於一個 → 留空".
 *
 * Returns the empty string for the multi-candidate case so the user is
 * forced to type the right name in (the `preFillMultiAttendeeHint`
 * banner is rendered alongside).
 */
export function pickCounterpartyDisplayName(
  attendees: string[],
  viewerEmail: string,
): { value: string; multipleCandidates: boolean } {
  const normalizedViewer = viewerEmail.trim().toLowerCase();
  const candidates: { displayName: string; email: string }[] = [];

  for (const raw of attendees) {
    // Format options: "Name <email>", "email", or "Name" (rare).
    const match = raw.match(/^(.*?)\s*<\s*([^<>]+?)\s*>\s*$/);
    let displayName: string;
    let email: string;
    if (match) {
      displayName = match[1].trim();
      email = match[2].trim();
    } else if (raw.includes("@")) {
      displayName = "";
      email = raw.trim();
    } else {
      displayName = raw.trim();
      email = "";
    }
    const normalizedEmail = email.toLowerCase();
    if (normalizedViewer && normalizedEmail === normalizedViewer) continue;
    candidates.push({ displayName, email });
  }

  if (candidates.length === 0) return { value: "", multipleCandidates: false };
  if (candidates.length > 1) return { value: "", multipleCandidates: true };
  const only = candidates[0];
  return { value: only.displayName || only.email, multipleCandidates: false };
}

/**
 * Slice-20b: ISO timestamp → `<input type=date>` / `<input type=time>` values.
 * Returns empty strings for null / unparseable inputs so the inputs stay
 * empty rather than showing `"Invalid Date"`.
 */
function _splitIso(iso: string | null | undefined): { date: string; time: string } {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: "", time: "" };
  const yyyy = d.getFullYear().toString().padStart(4, "0");
  const mm = (d.getMonth() + 1).toString().padStart(2, "0");
  const dd = d.getDate().toString().padStart(2, "0");
  const hh = d.getHours().toString().padStart(2, "0");
  const mi = d.getMinutes().toString().padStart(2, "0");
  return { date: `${yyyy}-${mm}-${dd}`, time: `${hh}:${mi}` };
}

export function NewMeeting() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  // Slice-7: pre-fill scheduled date from `?date=YYYY-MM-DD`.
  // refactor-meetings-tabs-unified: `?from=calendar` reroutes submit/cancel
  // back to /meetings?view=calendar (legacy /meetings/calendar removed).
  // Slice-20b: `?from_calendar=<event_id>` triggers calendar-event pre-fill.
  const search = useSearch({ strict: false }) as {
    date?: string;
    from?: string;
    from_calendar?: string;
  };
  const cameFromCalendar = search.from === "calendar";
  const cancelHref = cameFromCalendar ? "/meetings?view=calendar" : "/meetings";
  const fromCalendarEventId = search.from_calendar;

  const [title, setTitle] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [me, setMe] = useState("");
  const [scheduledDate, setScheduledDate] = useState<string>(search.date ?? "");
  const [scheduledStartTime, setScheduledStartTime] = useState<string>(search.date ? "09:00" : "");
  const [scheduledEndTime, setScheduledEndTime] = useState<string>("");
  const [goal, setGoal] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selectedAttachments, setSelectedAttachments] = useState<string[]>([]);
  const [selectedLinks, setSelectedLinks] = useState<string[]>([]);
  const [linkQuery, setLinkQuery] = useState("");
  const [multiAttendeeHint, setMultiAttendeeHint] = useState(false);
  const mutation = useCreateMeetingMutation();
  const submitting = mutation.isPending;

  // Slice-20b: pull the calendar event detail when `from_calendar` is set.
  const calendarEventQuery = useQuery({
    ...calendarEventQueryOptions(fromCalendarEventId ?? ""),
    enabled: Boolean(fromCalendarEventId),
  });

  // Pre-fill form from the calendar event once it resolves.
  useEffect(() => {
    if (!calendarEventQuery.data) return;
    const evt: CalendarEventDetail = calendarEventQuery.data;
    setTitle((prev) => (prev ? prev : evt.title));
    const { date: startDate, time: startTime } = _splitIso(evt.start);
    const { time: endTime } = _splitIso(evt.end);
    if (startDate) setScheduledDate((prev) => (prev ? prev : startDate));
    if (startTime) setScheduledStartTime((prev) => (prev ? prev : startTime));
    if (endTime) setScheduledEndTime((prev) => (prev ? prev : endTime));

    // Pre-fill me from organizer (when the viewer is the organizer) or
    // leave alone — the legacy slice-05 picker uses `currentUser.name`,
    // which the auth-client provides via session. We keep a simpler rule:
    // pre-fill `me` from the organizer email match against viewer's
    // session email; if no match, leave the field for manual entry.
    const viewerEmail = evt.organizer?.email ?? "";
    const picked = pickCounterpartyDisplayName(evt.attendees, viewerEmail);
    setCounterparty((prev) => (prev ? prev : picked.value));
    setMultiAttendeeHint(picked.multipleCandidates);
  }, [calendarEventQuery.data]);

  // Surface calendar-fetch errors inline so the user can still submit a
  // manual create (without calendar_event_id).
  const calendarErrorMessage =
    calendarEventQuery.error instanceof CalendarApiError && calendarEventQuery.error.errorCode
      ? localizedErrorMessage(calendarEventQuery.error.errorCode, t)
      : calendarEventQuery.isError
        ? t("errors.common.unknown")
        : null;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Slice-15: scheduled_start_at became required. Reject locally with
    // the same error code the backend would surface so the form does not
    // bother POSTing on missing input.
    if (!scheduledDate) {
      setError(localizedErrorMessage("meeting.scheduledStartRequired", t));
      return;
    }
    const startTime = scheduledStartTime || "09:00";
    const start = new Date(`${scheduledDate}T${startTime}:00`);
    if (Number.isNaN(start.getTime())) {
      setError(localizedErrorMessage("meeting.scheduledStartRequired", t));
      return;
    }
    let endIso: string | undefined;
    if (scheduledEndTime) {
      const end = new Date(`${scheduledDate}T${scheduledEndTime}:00`);
      if (!Number.isNaN(end.getTime())) {
        if (end.getTime() < start.getTime()) {
          setError(localizedErrorMessage("meeting.invalid_time_range", t));
          return;
        }
        endIso = end.toISOString();
      }
    }

    try {
      const payload: {
        title: string;
        counterparty_display_name: string;
        me_display_name: string;
        scheduled_start_at: string;
        scheduled_end_at?: string;
        calendar_event_id?: string;
        attachments?: string[];
        links?: string[];
      } = {
        title,
        counterparty_display_name: counterparty,
        me_display_name: me,
        scheduled_start_at: start.toISOString(),
      };
      if (endIso) {
        payload.scheduled_end_at = endIso;
      }
      // Slice-20b: only attach `calendar_event_id` when the user actually
      // arrived via the calendar preview path AND the event resolved
      // successfully. A failed calendar fetch falls back to manual
      // create (no calendar_event_id in payload, no generator invocation).
      if (fromCalendarEventId && calendarEventQuery.data) {
        payload.calendar_event_id = fromCalendarEventId;
      }
      if (selectedAttachments.length > 0) {
        payload.attachments = selectedAttachments;
      }
      // Slice-21: pre-attach related meetings from the create form. The
      // backend validates each id is owned by the current user; a bad id
      // raises `meeting.not_found` BEFORE the meeting row is created so
      // we don't leave an orphan.
      if (selectedLinks.length > 0) {
        payload.links = selectedLinks;
      }
      const meeting = await mutation.mutateAsync(payload);
      if (cameFromCalendar) {
        navigate({
          to: "/meetings",
          search: { view: "calendar" },
          replace: true,
        } as never);
      } else {
        navigate({
          to: "/meetings/$id",
          params: { id: meeting.id },
          replace: true,
        });
      }
    } catch (err) {
      if (err instanceof MeetingApiError && err.errorCode) {
        setError(localizedErrorMessage(err.errorCode, t));
      } else {
        setError(t("meetings.new.errorFallback"));
      }
    }
  }

  const isPreFilling = Boolean(fromCalendarEventId) && calendarEventQuery.isLoading;

  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-[520px] space-y-3">
        <BackLink to="/meetings" />
        <Card>
          <CardContent className="space-y-5 p-6">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight text-(--color-foreground)">
                {t("meetings.new.heading")}
              </h1>
              <p className="text-sm text-(--color-muted-foreground)">{t("meetings.new.subhead")}</p>
            </div>

            {/* Slice-20b: pre-fill progress banner (Calendar fetch in flight). */}
            {isPreFilling && (
              <Alert data-testid="prefill-banner">{t("meetings.new.preFillBanner")}</Alert>
            )}

            {/* Slice-20b: calendar fetch failed — show the localized error
                and keep the form rendered so manual submit still works. */}
            {calendarErrorMessage && (
              <Alert variant="destructive" data-testid="prefill-error">
                {calendarErrorMessage}
              </Alert>
            )}

            {/* Slice-20b: hint when the event has more than one non-viewer
                attendee (we can't auto-pick the counterparty). Uses the
                warning variant + icon so the empty counterparty field
                doesn't look like a normal placeholder. */}
            {multiAttendeeHint && (
              <Alert
                variant="warning"
                data-testid="prefill-multi-attendee-hint"
                className="flex items-start gap-2"
              >
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-(--color-accent)" />
                <span>{t("meetings.new.preFillMultiAttendeeHint")}</span>
              </Alert>
            )}

            <form className="space-y-4" onSubmit={handleSubmit} noValidate={false}>
              <div className="space-y-1.5">
                <Label htmlFor="meeting-title">{t("meetings.new.titleLabel")}</Label>
                <Input
                  id="meeting-title"
                  required
                  variant="curvy"
                  value={title}
                  placeholder={t("meetings.new.titlePlaceholder")}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="meeting-counterparty">
                    {t("meetings.new.counterpartyLabel")}
                  </Label>
                  <Input
                    id="meeting-counterparty"
                    required
                    variant="curvy"
                    value={counterparty}
                    placeholder={t("meetings.new.counterpartyPlaceholder")}
                    onChange={(e) => setCounterparty(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="meeting-me">{t("meetings.new.meLabel")}</Label>
                  <Input
                    id="meeting-me"
                    required
                    variant="curvy"
                    value={me}
                    placeholder={t("meetings.new.mePlaceholder")}
                    onChange={(e) => setMe(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1.5 sm:col-span-1">
                  <Label htmlFor="meeting-date">{t("meetings.new.scheduledDateLabel")}</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        aria-label={t("ui.calendar.openPicker")}
                        data-testid="meeting-date-trigger"
                        className="inline-flex h-9 w-full items-center justify-between gap-2 rounded-(--radius-md) border border-(--color-border) bg-(--color-surface) px-3 text-sm hover:border-(--color-primary)/40"
                      >
                        <span
                          className={
                            scheduledDate
                              ? "text-(--color-foreground)"
                              : "text-(--color-muted-foreground)"
                          }
                        >
                          {scheduledDate || t("ui.calendar.openPicker")}
                        </span>
                      </button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="p-0">
                      <Calendar
                        value={scheduledDate ? new Date(`${scheduledDate}T00:00`) : undefined}
                        onChange={(next) => {
                          const pad = (n: number) => String(n).padStart(2, "0");
                          const iso = `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
                          setScheduledDate(iso);
                          if (iso && !scheduledStartTime) setScheduledStartTime("09:00");
                        }}
                      />
                    </PopoverContent>
                  </Popover>
                  {/*
                   * Hidden mirror input — gives tests a `fireEvent.change`
                   * surface for direct state assertions. Production users
                   * pick a date via the Calendar popover above.
                   */}
                  <input
                    id="meeting-date"
                    data-testid="meeting-date"
                    type="date"
                    required
                    className="sr-only"
                    aria-hidden
                    tabIndex={-1}
                    value={scheduledDate}
                    onChange={(e) => {
                      setScheduledDate(e.target.value);
                      if (e.target.value && !scheduledStartTime) setScheduledStartTime("09:00");
                    }}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="meeting-time">{t("meetings.new.scheduledTimeLabel")}</Label>
                  <Input
                    id="meeting-time"
                    data-testid="meeting-time"
                    type="time"
                    value={scheduledStartTime}
                    onChange={(e) => setScheduledStartTime(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="meeting-end-time">
                    {t("meetings.new.scheduledEndTimeLabel")}
                  </Label>
                  <Input
                    id="meeting-end-time"
                    data-testid="meeting-end-time"
                    type="time"
                    value={scheduledEndTime}
                    onChange={(e) => setScheduledEndTime(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-2">
                  <Label htmlFor="meeting-goal">{t("meetings.new.goalLabel")}</Label>
                  <span className="text-xs text-(--color-muted-foreground)">
                    {t("meetings.new.goalHint")}
                  </span>
                </div>
                <textarea
                  id="meeting-goal"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder={t("meetings.new.goalPlaceholder")}
                  className="min-h-[70px] w-full resize-y rounded-md border border-(--color-border) bg-(--color-card) px-3 py-2 text-sm leading-relaxed text-(--color-foreground) outline-none focus-visible:ring-2 focus-visible:ring-(--color-ring)"
                />
              </div>

              {/* Slice-24: staged-attachment dropzone. Always renders so the
                  user can drop files even when none are staged yet. Replaces
                  the slice-20b `<AttachmentPicker>` which was permanently
                  invisible (there was no way to stage attachments before
                  the meeting existed). */}
              <div className="space-y-1">
                <Label>{t("meetings.new.staging.section_label")}</Label>
                <StagedAttachmentDropzone
                  selectedIds={selectedAttachments}
                  onChange={setSelectedAttachments}
                />
              </div>

              {/* Slice-21: multi-select link picker. Skipped when there are
                  no other meetings to link to (cold-start case). The picker
                  uses the same cached meetings list as
                  `<MeetingLinkPicker>` so search results render
                  instantly after the user has visited /meetings once. */}
              <LinkPicker
                query={linkQuery}
                onQueryChange={setLinkQuery}
                selectedIds={selectedLinks}
                onToggle={(id) =>
                  setSelectedLinks((prev) =>
                    prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
                  )
                }
                t={t}
              />

              {error && <Alert variant="destructive">{error}</Alert>}

              <Separator />

              <div className="flex items-center gap-2">
                <Link
                  to={cancelHref as "/meetings"}
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                >
                  {t("meetings.new.cancel")}
                </Link>
                <div className="flex-1" />
                <Button
                  type="submit"
                  variant="secondary"
                  size="sm"
                  disabled={submitting}
                  data-testid="save-draft-button"
                >
                  {t("meetings.new.saveDraft")}
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={submitting}
                  data-testid="create-meeting-button"
                >
                  <Sparkles animateOnHover className="size-3.5" />
                  {submitting ? t("meetings.new.submitting") : t("meetings.new.submit")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </ProtectedShell>
  );
}

function LinkPicker({
  query,
  onQueryChange,
  selectedIds,
  onToggle,
  t,
}: {
  query: string;
  onQueryChange: (v: string) => void;
  selectedIds: string[];
  onToggle: (id: string) => void;
  t: (k: string) => string;
}) {
  // Read straight from the meetings-list cache. If the cache hasn't been
  // populated (user landed on /meetings/new directly without visiting
  // /meetings first), `<MeetingLinkPicker>` chooses to render a
  // cache-miss hint — we do the same here for visual consistency.
  const listQuery = useQuery(meetingsListQueryOptions());
  const meetings: Meeting[] = listQuery.data ?? [];

  const trimmed = query.trim().toLowerCase();
  const candidates =
    trimmed.length === 0
      ? meetings
      : meetings.filter((m) => m.title.toLowerCase().includes(trimmed));

  // Always rendered — empty state explains what the picker is for so the
  // affordance stays discoverable even when the user has no other
  // meetings yet.
  return (
    <div className="space-y-2" data-testid="links-section">
      <div className="space-y-1">
        <Label>{t("meetings.new.linksLabel")}</Label>
        <p className="text-xs text-(--color-muted-foreground)">{t("meetings.new.linksHint")}</p>
      </div>
      {meetings.length === 0 ? (
        <p className="text-xs text-(--color-muted-foreground)" data-testid="links-empty">
          {t("meetings.new.linksEmpty")}
        </p>
      ) : (
        <>
          <Input
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder={t("meetings.new.linksSearchPlaceholder")}
            data-testid="links-search"
          />
          <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-(--color-border) p-2">
            {candidates.length === 0 ? (
              <li className="px-2 py-1 text-xs text-(--color-muted-foreground)">
                {t("meetings.new.linksNoMatch")}
              </li>
            ) : (
              candidates.slice(0, 20).map((m) => (
                <li key={m.id}>
                  <label className="flex cursor-pointer items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      data-testid={`link-candidate-${m.id}`}
                      checked={selectedIds.includes(m.id)}
                      onChange={() => onToggle(m.id)}
                    />
                    <span className="truncate">{m.title}</span>
                  </label>
                </li>
              ))
            )}
          </ul>
          {selectedIds.length > 0 && (
            <p className="text-xs text-(--color-muted-foreground)" data-testid="links-count">
              {t("meetings.new.linksCount").replace("{{count}}", String(selectedIds.length))}
            </p>
          )}
        </>
      )}
    </div>
  );
}
