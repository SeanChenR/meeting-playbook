/**
 * SettingsLayout — slice-19 polish (Sean revision 3).
 *
 * Single-page scrollable settings. The left rail is sticky, content stack
 * fills the rest of the protected-shell width (no extra max-w cap — the
 * shell already constrains to 1600px). Sub-nav links are in-page anchors.
 */

import { ProtectedShell } from "../protected-shell";
import { SettingsAllSections } from "./all-sections";
import { SettingsSubNav } from "./sub-nav";

export function SettingsLayout() {
  return (
    <ProtectedShell>
      <div
        data-testid="settings-layout"
        className="grid grid-cols-1 gap-6 md:grid-cols-[200px_minmax(0,1fr)]"
      >
        <aside className="md:sticky md:top-20 md:self-start">
          <SettingsSubNav />
        </aside>
        <section data-testid="settings-content" className="min-w-0 space-y-10">
          <SettingsAllSections />
        </section>
      </div>
    </ProtectedShell>
  );
}
