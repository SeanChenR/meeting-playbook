/**
 * /settings/integrations — Sean revision 3 hero treatment.
 *
 * Centered card with the Google Calendar logo as the dominant visual at
 * the top. The connection panel sits below; CalendarIntegrationPanel's
 * own header is suppressed in this context because the hero already
 * names the integration.
 */

import { useTranslation } from "react-i18next";
import { CalendarIntegrationPanel } from "../../components/calendar/calendar-integration-panel";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";

export function SettingsIntegrations() {
  const { t } = useTranslation();
  return (
    <GradientCardFrame
      data-testid="settings-integrations-card"
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
    >
      <div className="flex flex-col items-center rounded-[inherit] p-8">
        <div className="flex flex-col items-center gap-3 pb-6 text-center">
          <img
            src="/icons/google-calendar.png"
            alt=""
            aria-hidden
            className="size-20 drop-shadow-md"
          />
          <h2 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
            {t("settings.integrations.title")}
          </h2>
          <p className="max-w-md text-sm text-(--color-muted-foreground)">
            {t("settings.integrations.subhead")}
          </p>
        </div>
        <div className="w-full">
          <CalendarIntegrationPanel hideHeader />
        </div>
      </div>
    </GradientCardFrame>
  );
}
