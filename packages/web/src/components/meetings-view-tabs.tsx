/**
 * MeetingsViewTabs — slice meetings-ux-revamp tasks 3.1 + 3.2.
 *
 * Shared tab bar mounted on both /meetings (Kanban) and
 * /meetings/calendar (行事曆). The component is fully controlled — the
 * parent passes its current `value` and onValueChange triggers a
 * router navigation. URL is the single source of truth for which tab
 * is active.
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
    navigate({ to: next === "calendar" ? "/meetings/calendar" : "/meetings" });
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
