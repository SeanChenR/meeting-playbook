/**
 * Central code-based route tree for the web app.
 *
 * Lives in its own module so tests can import the same tree and build an
 * ad-hoc router with `createMemoryHistory`, while production wires it via
 * `App.tsx` with `createRouter` + `RouterProvider`.
 */

import { createRootRoute, createRoute, Outlet, redirect } from "@tanstack/react-router";
import { SettingsLayout } from "./components/settings/layout";
import { DashboardPage } from "./routes/DashboardPage";
import { Login } from "./routes/login";
import { MeetingDetail } from "./routes/meetings/detail";
import { MeetingsCalendar } from "./routes/meetings/calendar";
import { MeetingsList } from "./routes/meetings/list";
import { NewMeeting } from "./routes/meetings/new";
import { UpcomingEvents } from "./routes/calendar/upcoming";
import { Signup } from "./routes/signup";
import { TotpEnroll } from "./routes/totp/enroll";
import { TotpVerify } from "./routes/totp/verify";

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

// Slice-18 v2 (Sean revision): HomePage removed entirely — the 4-region
// dashboard duplicated /meetings. Root now redirects to /meetings so the
// kanban-style meetings view is the de-facto landing surface.
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/meetings" });
  },
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: Login,
});

const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signup",
  component: Signup,
});

const totpEnrollRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/totp/enroll",
  component: TotpEnroll,
});

const totpVerifyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/totp/verify",
  component: TotpVerify,
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  component: DashboardPage,
});

const meetingsListRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/meetings",
  component: MeetingsList,
});

const meetingsNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/meetings/new",
  component: NewMeeting,
});

const meetingsCalendarRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/meetings/calendar",
  component: MeetingsCalendar,
});

const meetingDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/meetings/$id",
  component: MeetingDetail,
});

// Slice-7: rename `/calendar` → `/calendar/import` to disambiguate from
// `/meetings/calendar` (the new calendar VIEW). The component + file name
// stays as `routes/calendar/upcoming.tsx` — only the URL path changes.
const calendarImportRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/calendar/import",
  component: UpcomingEvents,
});

// Slice-19 v3 (Sean revision): `/settings` is now a single scrollable page
// — all six former sub-pages render as stacked anchor sections under one
// URL. Legacy deep links (`/settings/profile`, `/settings/security`, …)
// redirect to `/settings#<id>` so any in-flight bookmark / shortcut still
// lands on the right section.
const settingsLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsLayout,
});

function _legacySubRouteRedirect(hash: string) {
  return () => {
    throw redirect({ to: "/settings", hash });
  };
}

const settingsProfileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/profile",
  beforeLoad: _legacySubRouteRedirect("profile"),
});

const settingsSecurityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/security",
  beforeLoad: _legacySubRouteRedirect("security"),
});

const settingsIntegrationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/integrations",
  beforeLoad: _legacySubRouteRedirect("integrations"),
});

const settingsVoiceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/voice",
  beforeLoad: _legacySubRouteRedirect("voice"),
});

const settingsPreferencesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/preferences",
  beforeLoad: _legacySubRouteRedirect("preferences"),
});

const settingsDataRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/data",
  beforeLoad: _legacySubRouteRedirect("data"),
});

// Slice-17 was top-level `/settings/tags`; post-slice-19 the page is a
// section in the single-page /settings. Keep the legacy path as a redirect
// so any bookmark / external link lands on the right anchor.
const settingsTagsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/tags",
  beforeLoad: _legacySubRouteRedirect("tags"),
});

export const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  signupRoute,
  totpEnrollRoute,
  totpVerifyRoute,
  dashboardRoute,
  meetingsListRoute,
  meetingsNewRoute,
  meetingsCalendarRoute,
  meetingDetailRoute,
  calendarImportRoute,
  settingsLayoutRoute,
  settingsProfileRoute,
  settingsSecurityRoute,
  settingsIntegrationsRoute,
  settingsVoiceRoute,
  settingsPreferencesRoute,
  settingsDataRoute,
  settingsTagsRoute,
]);
