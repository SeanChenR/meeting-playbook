/**
 * RerunButton — slice-11 task 6.1.
 *
 * Visible iff `meeting.status === "completed" && recordings_available
 * && !rerun_asr_pending`. Click → POST /api/meetings/{id}/rerun_asr.
 *
 * On 202 we optimistically flip the local `rerun_asr_pending` flag in the
 * cache so the button hides immediately (the polling status hook owned by
 * the parent will then take over and fetch the actual progress shape).
 *
 * On 409/410/422 we surface the localised error inline; 4xx after the row
 * was rendered means the user's local state is stale, so we also invalidate
 * the meeting query so the next render gets the corrected gating.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { localizedErrorMessage } from "../lib/i18n-errors";
import type { MeetingDetail } from "../lib/meetings-api";
import { type RerunApiError, startRerun } from "../lib/rerun-api";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";

interface RerunButtonProps {
  meeting: Pick<MeetingDetail, "id" | "status" | "recordings_available" | "rerun_asr_pending">;
  /** When true, render the button even if it isn't currently actionable —
   *  the unusable cases just disable the button. Used by the action bar so
   *  the affordance row keeps a stable shape (Sean: "不能用就 disable 掉就好"). */
  alwaysRender?: boolean;
  /** Optional override for the button label (e.g. icon-prefixed version). */
  children?: ReactNode;
}

export function RerunButton({ meeting, alwaysRender = false, children }: RerunButtonProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const visible =
    meeting.status === "completed" && meeting.recordings_available && !meeting.rerun_asr_pending;

  const mutation = useMutation({
    mutationFn: () => startRerun(meeting.id),
    onSuccess: () => {
      // Optimistic: flip pending flag in the cached meeting row so the
      // button hides immediately (otherwise it would briefly stay clickable
      // until the next meeting refetch).
      queryClient.setQueryData<MeetingDetail>(["meetings", meeting.id], (prev) =>
        prev ? { ...prev, rerun_asr_pending: true } : prev,
      );
      queryClient.invalidateQueries({ queryKey: ["rerun_status", meeting.id] });
    },
    onError: () => {
      // 4xx after the gating passed = stale local state. Refetch so the
      // next render reflects the truth.
      queryClient.invalidateQueries({ queryKey: ["meetings", meeting.id] });
    },
  });

  if (!visible && !alwaysRender) return null;

  const errorCode = mutation.error ? (mutation.error as RerunApiError).errorCode : undefined;
  const errorMessage = errorCode ? localizedErrorMessage(errorCode, t) : null;

  // alwaysRender path: still render the button but disable it when not
  // actionable so the affordance row doesn't reflow as session state changes.
  const disabled = !visible || mutation.isPending;

  return (
    <div className="flex flex-col gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            size="sm"
            variant="outline"
            data-testid="rerun-button"
            onClick={() => mutation.mutate()}
            disabled={disabled}
          >
            {children ?? t("meetings.detail.rerunButton")}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("ui.tooltip.rerun")}</TooltipContent>
      </Tooltip>
      {errorMessage ? (
        <span className="text-xs text-(--color-destructive)">{errorMessage}</span>
      ) : null}
    </div>
  );
}
