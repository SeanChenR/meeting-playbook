/**
 * HeadphonesHint — informational callout above Start Meeting button.
 *
 * Slice-7 round 2: BlackHole's Multi-Output Device routes system audio to
 * BOTH speakers AND BlackHole. Without headphones, the mic picks up the
 * speakers, and `me.wav` ends up containing the same content as
 * `counterparty.wav` — both streams duplicate. Per design.md "Echo loop
 * UX" decision, we don't implement DSP echo cancellation; the user-facing
 * mitigation is this hint plus the BLACKHOLE_SETUP.md callout.
 *
 * Visible only when `meeting.status === "scheduled"`. Permanent (no
 * dismiss button) — disappears naturally when the session starts.
 */

import { useTranslation } from "react-i18next";
import { Alert } from "./ui/alert";

export interface HeadphonesHintProps {
  visible: boolean;
}

export function HeadphonesHint({ visible }: HeadphonesHintProps) {
  const { t } = useTranslation();
  if (!visible) return null;
  return (
    <Alert data-testid="headphones-hint" variant="warning" role="note">
      {t("meetings.session.headphonesHint")}
    </Alert>
  );
}
