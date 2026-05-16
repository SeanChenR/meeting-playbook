/**
 * MeetingsViewTabs — slice meetings-ux-revamp tasks 3.1 + 3.2.
 *
 * Shared tab bar mounted on both /meetings (Kanban) and
 * /meetings/calendar (行事曆). The component is fully controlled — the
 * parent passes its current `value` and onValueChange triggers a
 * router navigation. URL is the single source of truth for which tab
 * is active.
 */

import { useLocation, useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { Tabs, TabsList, TabsTrigger } from "./ui/tabs";

export type MeetingsView = "kanban" | "calendar";

export interface MeetingsViewTabsProps {
  value: MeetingsView;
}

export function MeetingsViewTabs({ value }: MeetingsViewTabsProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const handleChange = (next: string) => {
    if (next === value) return;
    // Slice-17: preserve cross-view search params (notably `?tag_ids=`) so
    // the TagFilter selection survives a tab switch. Re-parse from the raw
    // searchStr so TanStack Router doesn't strip unknown keys via the
    // route's search validator (the meetings list / calendar routes have
    // no strict schema yet).
    // `URLSearchParams` strips a leading `?` itself, no need to slice.
    const params = new URLSearchParams(location.searchStr ?? "");
    const searchObj: Record<string, string> = {};
    params.forEach((v, k) => {
      searchObj[k] = v;
    });
    navigate({
      to: next === "calendar" ? "/meetings/calendar" : "/meetings",
      search: () => searchObj,
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
