/**
 * SettingsAllSections — slice-19 polish (Sean revision 3).
 *
 * Renders every settings sub-page as a stacked anchor section under one
 * `/settings` URL. Each section carries `id="<key>"` + `scroll-mt-24` so
 * sticky-nav anchor links land below the protected-shell NavBar.
 *
 * The section components themselves still live in `routes/settings/*.tsx`
 * — this file just composes them with section headings + IDs.
 */

import { useTranslation } from "react-i18next";
import { SettingsData } from "../../routes/settings/data";
import { SettingsIntegrations } from "../../routes/settings/integrations";
import { SettingsPreferences } from "../../routes/settings/preferences";
import { SettingsProfile } from "../../routes/settings/profile";
import { SettingsSecurity } from "../../routes/settings/security";
import { SettingsTags } from "../../routes/settings/tags";
import { SettingsVoice } from "../../routes/settings/voice";

interface SectionDef {
  id: string;
  key: string;
  Body: () => React.ReactElement;
}

const _SECTIONS: SectionDef[] = [
  { id: "profile", key: "profile", Body: SettingsProfile },
  { id: "security", key: "security", Body: SettingsSecurity },
  { id: "integrations", key: "integrations", Body: SettingsIntegrations },
  { id: "voice", key: "voice", Body: SettingsVoice },
  { id: "tags", key: "tags", Body: SettingsTags },
  { id: "preferences", key: "preferences", Body: SettingsPreferences },
  { id: "data", key: "data", Body: SettingsData },
];

export function SettingsAllSections() {
  const { t } = useTranslation();
  return (
    <>
      {_SECTIONS.map(({ id, key, Body }) => (
        <section
          key={id}
          id={id}
          data-testid={`settings-section-${id}`}
          className="scroll-mt-24 space-y-3"
        >
          <h2 className="text-lg font-semibold tracking-tight text-(--color-foreground)">
            {t(`settings.nav.${key}`)}
          </h2>
          <Body />
        </section>
      ))}
    </>
  );
}
