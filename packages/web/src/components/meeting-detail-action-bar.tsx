/**
 * MeetingDetailActionBar — Management Bar style 3-segment controls row.
 *
 * Outer chrome: a single rounded "bar" (surface + ring + shadow) that visually
 * groups every control under the title. Sean asked for the animate-ui
 * Management Bar feel — pill-shaped controls inside a chunky container with
 * vertical separators between functional groups.
 *
 *   Left:   [Start/End] [Edit] [Upload] [Rerun] [Export] | [Delete (filled red)]
 *           Start/End is a single toggle button; everything else stays visible
 *           across states and disables when not applicable.
 *
 *   Middle: [附件 N] [相關會議 N]  — coloured count chips (primary / accent).
 *
 *   Right:  [錄音模式 card] [ASR 引擎 card] — clickable info cards.
 */

import {
  Check,
  ChevronDown,
  Headphones,
  Link2,
  Mic,
  Paperclip,
  Pencil,
  Play,
  RotateCw,
  Square,
  Trash2,
  Upload,
} from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { MeetingBucket, MeetingDetail } from "../lib/meetings-api";
import { cn } from "../lib/utils";
import { ExportMeetingButton } from "./export-meeting-button";
import { ShineBorder } from "./magicui/shine-border";
import type { MeetingPhase } from "./meeting-header-bar";
import { RerunButton } from "./rerun-button";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

export interface MeetingDetailActionBarProps {
  bucket: MeetingBucket;
  phase: MeetingPhase;
  startDisabled: boolean;
  onStart: () => void;
  onEnd: () => void;
  onEdit: () => void;
  onUpload: () => void;
  onDelete: () => void;
  meeting: Pick<MeetingDetail, "id" | "status" | "recordings_available" | "rerun_asr_pending">;
  meetingTitle: string;
  scheduledStartAt: string | null;
  onExportSuccess: () => void;

  // Middle segment (counts)
  attachmentsCount: number;
  linksCount: number;
  onAttachmentsOpen: () => void;
  onLinkedOpen: () => void;

  // Right segment (mode + ASR dropdowns)
  recordingMode: "dual" | "single" | null | undefined;
  asrProvider: string | null | undefined;
  /** Fires when user picks a new recording mode from the dropdown.
   *  Null = read-only (post-meeting). */
  onRecordingModeChange?: (mode: "dual" | "single") => void;
  /** Fires when user picks a new ASR engine from the dropdown.
   *  Null = read-only. */
  onAsrProviderChange?: (provider: "whisper" | "qwen3") => void;
}

/** Coloured count chip — pill with a tinted background per category.
 *  Sean: "附件和相關會議的部分，也做點顏色的渲染吧。" */
function _CountChip({
  icon,
  label,
  count,
  onClick,
  testId,
  tone,
}: {
  icon: ReactNode;
  label: string;
  count: number;
  onClick: () => void;
  testId: string;
  /** Aura colour token name (drives bg + ring + text colour). */
  tone: "primary" | "accent";
}) {
  const toneClasses =
    tone === "primary"
      ? "bg-(--color-primary)/10 ring-(--color-primary)/20 text-(--color-primary) hover:bg-(--color-primary)/16"
      : "bg-(--color-accent)/10 ring-(--color-accent)/20 text-(--color-accent) hover:bg-(--color-accent)/16";
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium ring-1",
        "transition-colors",
        toneClasses,
      )}
    >
      {icon}
      <span>{label}</span>
      <span className="ml-0.5 inline-flex min-w-[18px] items-center justify-center rounded-full bg-(--color-surface) px-1 text-[11px] font-semibold tabular-nums text-(--color-foreground)">
        {count}
      </span>
    </button>
  );
}

interface DropdownOption<T extends string> {
  value: T;
  label: string;
  icon: ReactNode;
}

function _InfoDropdown<T extends string>({
  label,
  current,
  options,
  onChange,
  testId,
}: {
  label: string;
  /** Currently-selected option (must match one of `options`). */
  current: T;
  options: ReadonlyArray<DropdownOption<T>>;
  onChange?: (next: T) => void;
  testId: string;
}) {
  const interactive = !!onChange;
  const active = options.find((opt) => opt.value === current);
  const trigger = (
    <button
      type="button"
      data-testid={testId}
      disabled={!interactive}
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-3 py-1",
        "bg-(--color-surface) ring-1 ring-(--color-border)/60 text-[12px]",
        interactive
          ? "transition-all hover:bg-(--color-surface-2) hover:ring-(--color-primary)/30 cursor-pointer"
          : "cursor-default",
      )}
    >
      {active?.icon}
      <span className="text-[11px] uppercase tracking-wider text-(--color-muted-foreground)">
        {label}
      </span>
      <span className="font-medium text-(--color-foreground)">{active?.label ?? current}</span>
      {interactive && (
        <ChevronDown
          className="size-3 text-(--color-muted-foreground)"
          strokeWidth={1.5}
          aria-hidden
        />
      )}
    </button>
  );

  if (!interactive) return trigger;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[200px]">
        <DropdownMenuLabel className="text-[11px] uppercase tracking-wider text-(--color-muted-foreground)">
          {label}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((opt) => {
          const isActive = opt.value === current;
          return (
            <DropdownMenuItem
              key={opt.value}
              data-testid={`${testId}-option-${opt.value}`}
              onSelect={() => onChange?.(opt.value)}
              className="flex items-center gap-2"
            >
              {opt.icon}
              <span className="flex-1 text-sm">{opt.label}</span>
              {isActive && (
                <Check className="size-3.5 text-(--color-primary)" strokeWidth={2} aria-hidden />
              )}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function MeetingDetailActionBar(props: MeetingDetailActionBarProps) {
  const { t } = useTranslation();
  const {
    bucket,
    phase,
    startDisabled,
    onStart,
    onEnd,
    onEdit,
    onUpload,
    onDelete,
    meeting,
    meetingTitle,
    scheduledStartAt,
    onExportSuccess,
    attachmentsCount,
    linksCount,
    onAttachmentsOpen,
    onLinkedOpen,
    recordingMode,
    asrProvider,
    onRecordingModeChange,
    onAsrProviderChange,
  } = props;

  const isLive = phase === "in_progress" || phase === "ending";
  const canStart = bucket === "upcoming" && phase === "idle" && !startDisabled;
  // Upload covers two cases:
  //   1. `needs_recording` bucket — the meeting was scheduled, the time
  //      passed, and the user wants to upload an offline recording later.
  //   2. `completed` meetings whose `recordings_available` is false — the
  //      live capture didn't persist anything (crashed mid-session, the
  //      user closed early, etc.). They should still be able to attach a
  //      recording for transcription.
  const canUpload =
    !isLive &&
    (bucket === "needs_recording" || (bucket === "completed" && !meeting.recordings_available));
  const canExport = bucket === "needs_recording" || bucket === "completed";
  const canDelete = !isLive;

  // Dropdown option lists — labels resolve via i18n; icons mix Lucide vector
  // glyphs (for recording mode) with raw PNG provider logos (for ASR engine,
  // matching the settings page).
  const modeOptions: ReadonlyArray<DropdownOption<"dual" | "single">> = [
    {
      value: "dual",
      label: t("meetings.detail.recordingMode.dual"),
      icon: (
        <Headphones
          className="size-3.5 text-(--color-muted-foreground)"
          strokeWidth={1.5}
          aria-hidden
        />
      ),
    },
    {
      value: "single",
      label: t("meetings.detail.recordingMode.single"),
      icon: (
        <Mic className="size-3.5 text-(--color-muted-foreground)" strokeWidth={1.5} aria-hidden />
      ),
    },
  ];

  const asrOptions: ReadonlyArray<DropdownOption<"whisper" | "qwen3">> = [
    {
      value: "whisper",
      label: "Whisper",
      icon: <img src="/icons/whisper.png" alt="" aria-hidden className="size-4 rounded-[3px]" />,
    },
    {
      value: "qwen3",
      label: "Qwen3-ASR",
      icon: <img src="/icons/qwen.png" alt="" aria-hidden className="size-4 rounded-[3px]" />,
    },
  ];

  // Normalise the current ASR provider key to one of the two known options.
  // Backend can ship variants like "whisper-large-v3" / "qwen3-asr"; we map
  // those into the dropdown's canonical bucket so the active item is marked.
  const asrCurrent: "whisper" | "qwen3" | null = asrProvider
    ? /whisper/i.test(asrProvider)
      ? "whisper"
      : /qwen/i.test(asrProvider)
        ? "qwen3"
        : null
    : null;

  return (
    <div
      data-testid="meeting-detail-action-bar"
      className={cn(
        "relative overflow-hidden rounded-2xl bg-(--color-surface)",
        "shadow-(--shadow-sm) ring-1 ring-(--color-border)/60",
      )}
    >
      <ShineBorder duration={12} />
      <div
        className={cn(
          "relative z-[1] flex flex-wrap items-center justify-between",
          "gap-x-6 gap-y-3 px-4 py-3",
        )}
      >
        {/* ── LEFT: action buttons + delete ────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          {isLive ? (
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={onEnd}
              data-testid="action-bar-end"
            >
              <Square className="size-3.5" strokeWidth={1.5} />
              {t("meetings.session.end")}
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={onStart}
              disabled={!canStart}
              data-testid="action-bar-start"
            >
              <Play className="size-3.5" strokeWidth={1.5} />
              {t("meetings.session.start")}
            </Button>
          )}

          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onEdit}
            disabled={isLive}
            data-testid="action-bar-edit"
          >
            <Pencil className="size-3.5" strokeWidth={1.5} />
            {t("meetings.detail.editAction")}
          </Button>

          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onUpload}
            disabled={!canUpload}
            data-testid="action-bar-upload"
            className={cn(!canUpload && "opacity-60")}
          >
            <Upload className="size-3.5" strokeWidth={1.5} />
            {t("meetings.session.uploadAudio")}
          </Button>

          <RerunButton meeting={meeting} alwaysRender>
            <RotateCw className="size-3.5" strokeWidth={1.5} />
            {t("meetings.detail.rerunButton")}
          </RerunButton>

          <ExportMeetingButton
            meetingId={meeting.id}
            meetingTitle={meetingTitle}
            scheduledStartAt={scheduledStartAt}
            onExportSuccess={onExportSuccess}
            disabled={!canExport}
          />

          {/* Vertical separator before destructive action */}
          <span aria-hidden className="mx-1 h-5 w-px bg-(--color-border)" />

          <Button
            type="button"
            size="sm"
            variant="destructive"
            onClick={onDelete}
            disabled={!canDelete}
            data-testid="action-bar-delete"
          >
            <Trash2 className="size-3.5" strokeWidth={1.5} />
            {t("meetings.detail.menu.delete")}
          </Button>
        </div>

        {/* ── MIDDLE: counts ───────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <_CountChip
            icon={<Paperclip className="size-3.5" strokeWidth={1.7} aria-hidden />}
            label={t("meetings.detail.menu.attachments")}
            count={attachmentsCount}
            onClick={onAttachmentsOpen}
            testId="meta-strip-attachments"
            tone="primary"
          />
          <_CountChip
            icon={<Link2 className="size-3.5" strokeWidth={1.7} aria-hidden />}
            label={t("meetings.detail.menu.linked")}
            count={linksCount}
            onClick={onLinkedOpen}
            testId="meta-strip-linked"
            tone="accent"
          />
        </div>

        {/* ── RIGHT: dropdown selectors (mode + ASR engine) ────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          {recordingMode && (
            <_InfoDropdown
              label={t("meetings.detail.recordingMode.label")}
              current={recordingMode}
              options={modeOptions}
              onChange={onRecordingModeChange}
              testId="meta-strip-mode"
            />
          )}

          {asrCurrent && (
            <_InfoDropdown
              label={t("meetings.detail.asrEngine.label")}
              current={asrCurrent}
              options={asrOptions}
              onChange={onAsrProviderChange}
              testId="meta-strip-asr"
            />
          )}
        </div>
      </div>
    </div>
  );
}
