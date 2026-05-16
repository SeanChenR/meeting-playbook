/**
 * DashboardPage — slice-18 task 5.2.
 *
 * Renders four chart blocks + a period switcher backed by
 * `useStatsQuery(range)`. Charts use Recharts with palette tokens
 * (`var(--primary)` / `var(--accent)`) so dark / light theme switches
 * propagate via CSS-variable reads.
 */

import { ProtectedShell } from "../components/protected-shell";
import { DashboardBody } from "../components/dashboard/dashboard-body";

export function DashboardPage() {
  return (
    <ProtectedShell>
      <div data-testid="dashboard-page" className="space-y-6">
        <DashboardBody />
      </div>
    </ProtectedShell>
  );
}
