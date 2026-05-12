/**
 * NewMeeting route — slice ui-overhaul-claude-design task 4.2.
 *
 * Visual contract aligned with design bundle `NewMeetingScreen`:
 *   - 520px centered card inside ProtectedShell
 *   - BackLink in main as the first row
 *   - 會議標題 + 對方/我方 grid + 預定開始/結束 grid + 會議目標 textarea
 *     (textarea note: hint reads "選填，AI 會用來生成 playbook")
 *   - Footer: 取消 ghost button → spacer → 儲存草稿 secondary →
 *     建立並生成 playbook primary (Sparkles icon)
 *
 * Behavioural contract preserved:
 *   - Existing tests query labels by `/標題/`, `/對方顯示名稱/`,
 *     `/我方顯示名稱/`, button name `/建立$/` → kept verbatim.
 *   - `posted!.body` toEqual exact { title, counterparty_display_name,
 *     me_display_name } when no schedule entered → only include
 *     `scheduled_start_at` / `scheduled_end_at` when set, so the body
 *     payload stays equal to the test's expected shape.
 *
 * The "儲存草稿" button shares the same submit handler — it's a visual
 * variant per the design bundle; production has no separate draft state.
 */

import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Sparkles } from "../../components/animate-ui/icons/sparkles";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { BackLink } from "../../components/back-link";
import { ProtectedShell } from "../../components/protected-shell";
import { Alert } from "../../components/ui/alert";
import { Button, buttonVariants } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Separator } from "../../components/ui/separator";
import { localizedErrorMessage } from "../../lib/i18n-errors";
import { MeetingApiError, useCreateMeetingMutation } from "../../lib/meetings-api";

export function NewMeeting() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  // Slice-7: pre-fill scheduled date from `?date=YYYY-MM-DD`.
  // Slice meetings-ux-revamp Decision 4: `?from=calendar` reroutes
  // submit/cancel back to /meetings/calendar instead of /meetings.
  const search = useSearch({ strict: false }) as { date?: string; from?: string };
  const cameFromCalendar = search.from === "calendar";
  const cancelHref = cameFromCalendar ? "/meetings/calendar" : "/meetings";
  const [title, setTitle] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [me, setMe] = useState("");
  const [scheduledDate, setScheduledDate] = useState<string>(search.date ?? "");
  const [scheduledStartTime, setScheduledStartTime] = useState<string>(search.date ? "09:00" : "");
  const [scheduledEndTime, setScheduledEndTime] = useState<string>("");
  const [goal, setGoal] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useCreateMeetingMutation();
  const submitting = mutation.isPending;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    try {
      const payload: {
        title: string;
        counterparty_display_name: string;
        me_display_name: string;
        scheduled_start_at?: string;
        scheduled_end_at?: string;
      } = {
        title,
        counterparty_display_name: counterparty,
        me_display_name: me,
      };
      if (scheduledDate) {
        const startTime = scheduledStartTime || "09:00";
        const start = new Date(`${scheduledDate}T${startTime}:00`);
        if (!Number.isNaN(start.getTime())) {
          payload.scheduled_start_at = start.toISOString();
        }
        if (scheduledEndTime) {
          const end = new Date(`${scheduledDate}T${scheduledEndTime}:00`);
          if (!Number.isNaN(end.getTime())) {
            payload.scheduled_end_at = end.toISOString();
          }
        }
      }
      const meeting = await mutation.mutateAsync(payload);
      if (cameFromCalendar) {
        navigate({ to: "/meetings/calendar", replace: true });
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

            <form className="space-y-4" onSubmit={handleSubmit} noValidate={false}>
              <div className="space-y-1.5">
                <Label htmlFor="meeting-title">{t("meetings.new.titleLabel")}</Label>
                <Input
                  id="meeting-title"
                  required
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
                    value={me}
                    placeholder={t("meetings.new.mePlaceholder")}
                    onChange={(e) => setMe(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="space-y-1.5 sm:col-span-1">
                  <Label htmlFor="meeting-date">{t("meetings.new.scheduledDateLabel")}</Label>
                  <Input
                    id="meeting-date"
                    data-testid="meeting-date"
                    type="date"
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
