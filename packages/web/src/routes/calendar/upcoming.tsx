/**
 * /calendar/import — slice-19 task 4.1 refactor.
 *
 * The page is now a thin wrapper around `<CalendarIntegrationPanel />` (the
 * extracted reusable surface) plus the legacy `BackLink` + `ProtectedShell`
 * frame. The same panel is rendered inside `/settings/integrations` without
 * the shell wrapper.
 *
 * Slice-19 task 3.3 (route-level redirect to /settings/integrations) is
 * deferred to a follow-up; both URLs currently render the same panel.
 */

import { BackLink } from "../../components/back-link";
import { CalendarIntegrationPanel } from "../../components/calendar/calendar-integration-panel";
import { ProtectedShell } from "../../components/protected-shell";

export function UpcomingEvents() {
  return (
    <ProtectedShell>
      <div className="mx-auto w-full max-w-[860px] space-y-4">
        <BackLink to="/meetings" />
        <CalendarIntegrationPanel />
      </div>
    </ProtectedShell>
  );
}
