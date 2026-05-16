/**
 * SettingsSubNav — slice-19 polish (Sean revision 3).
 *
 * Anchor-based nav: every link points to an in-page `#section-id` rather
 * than a separate route. We sync the active section with scroll position
 * via IntersectionObserver so the rail highlights what's currently in
 * view, the same UX as Apple Notes / Slack settings.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../lib/utils";

interface NavEntry {
  id: string;
  key: string;
}

const _ENTRIES: NavEntry[] = [
  { id: "profile", key: "profile" },
  { id: "security", key: "security" },
  { id: "integrations", key: "integrations" },
  { id: "voice", key: "voice" },
  { id: "tags", key: "tags" },
  { id: "preferences", key: "preferences" },
  { id: "data", key: "data" },
];

export function SettingsSubNav() {
  const { t } = useTranslation();
  const [activeId, setActiveId] = useState<string>(_ENTRIES[0]?.id ?? "");
  const ratiosRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const ratios = ratiosRef.current;
        for (const entry of entries) {
          const id = entry.target.id;
          if (!id) continue;
          ratios.set(id, entry.intersectionRatio);
        }
        // Pick the highest-visibility section; ignores fully off-screen ones.
        let bestId = "";
        let bestRatio = 0;
        for (const [id, r] of ratios.entries()) {
          if (r > bestRatio) {
            bestRatio = r;
            bestId = id;
          }
        }
        if (bestId) setActiveId(bestId);
      },
      {
        // 56px nav offset + 24px breathing room → trigger when the section
        // top crosses just below the sticky NavBar.
        rootMargin: "-80px 0px -40% 0px",
        threshold: [0.05, 0.25, 0.5, 0.75],
      },
    );
    for (const entry of _ENTRIES) {
      const el = document.getElementById(entry.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  return (
    <nav
      data-testid="settings-sub-nav"
      aria-label={t("settings.nav.menu_entry")}
      className="flex flex-col gap-0.5"
    >
      {_ENTRIES.map((entry) => {
        const active = activeId === entry.id;
        return (
          <a
            key={entry.id}
            href={`#${entry.id}`}
            data-testid={`settings-sub-nav-${entry.key}`}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-(--color-muted) text-(--color-foreground)"
                : "text-(--color-muted-foreground) hover:bg-(--color-muted) hover:text-(--color-foreground)",
            )}
          >
            {t(`settings.nav.${entry.key}`)}
          </a>
        );
      })}
    </nav>
  );
}
