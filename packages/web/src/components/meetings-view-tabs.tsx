/**
 * MeetingsViewTabs — refactor-meetings-tabs-unified.
 *
 * Shared tab bar mounted once by the /meetings wrapper. Switching toggles
 * the `?view` search param on the same route (no pathname change), so the
 * pill animates smoothly without remounting and other search params (e.g.
 * `tag_ids`) are preserved.
 */

import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "./ui/tabs";

export type MeetingsView = "kanban" | "calendar";

export interface MeetingsViewTabsProps {
  value: MeetingsView;
}

export function MeetingsViewTabs({ value }: MeetingsViewTabsProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleChange = (next: string) => {
    if (next === value) return;
    const nextView = next === "calendar" ? "calendar" : undefined;
    navigate({
      to: "/meetings",
      search: (prev: Record<string, unknown> | undefined) => ({
        ...(prev ?? {}),
        view: nextView,
      }),
    } as never);
  };

  return (
    <Tabs value={value} onValueChange={handleChange} data-testid="meetings-view-tabs">
      <TabsList className="h-9">
        <TabsTrigger value="kanban" data-testid="meetings-view-tab-kanban">
          {t("meetings.viewTabs.kanban")}
        </TabsTrigger>
        <TabsTrigger value="calendar" data-testid="meetings-view-tab-calendar">
          {t("meetings.viewTabs.calendar")}
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}
