/**
 * Central code-based route tree for the web app.
 *
 * Lives in its own module so tests can import the same tree and build an
 * ad-hoc router with `createMemoryHistory`, while production wires it via
 * `App.tsx` with `createRouter` + `RouterProvider`.
 */

import { createRootRoute, createRoute, Outlet, redirect } from "@tanstack/react-router";
import { Home } from "./routes/home";
import { Login } from "./routes/login";
import { MeetingDetail } from "./routes/meetings/detail";
import { MeetingsCalendar } from "./routes/meetings/calendar";
import { MeetingsList } from "./routes/meetings/list";
import { NewMeeting } from "./routes/meetings/new";
import { UpcomingEvents } from "./routes/calendar/upcoming";
import { SettingsVoice } from "./routes/settings/voice";
import { Signup } from "./routes/signup";
import { TotpEnroll } from "./routes/totp/enroll";
import { TotpVerify } from "./routes/totp/verify";

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

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

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/home",
  component: Home,
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

// Slice-13: standalone /settings/voice (no /settings shell yet — will be
// folded into the sub-nav when slice-19 ships).
const settingsVoiceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings/voice",
  component: SettingsVoice,
});

export const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  signupRoute,
  totpEnrollRoute,
  totpVerifyRoute,
  homeRoute,
  meetingsListRoute,
  meetingsNewRoute,
  meetingsCalendarRoute,
  meetingDetailRoute,
  calendarImportRoute,
  settingsVoiceRoute,
]);
