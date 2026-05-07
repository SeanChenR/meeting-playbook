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
import { MeetingsList } from "./routes/meetings/list";
import { NewMeeting } from "./routes/meetings/new";
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

const meetingDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/meetings/$id",
  component: MeetingDetail,
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
  meetingDetailRoute,
]);
