import type { ReactNode } from "react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "@tanstack/react-router";
import { authClient } from "../lib/auth-client";
import { LocaleToggle } from "./locale-toggle";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";

export interface ProtectedShellProps {
  children: ReactNode;
  /**
   * Slice-07: when true, the main content area drops its centered max-width
   * container so the page can use the full viewport width.
   * The detail page passes `fullBleed` so its 3-column / stack workspace
   * isn't squashed into a 1200px column.
   */
  fullBleed?: boolean;
}

/**
 * ProtectedShell — slice-18 task 3.2.
 *
 * NavBar exposes three top-level destinations (`/`, `/meetings`, `/dashboard`)
 * and routes Locale / Theme / Settings / Logout into the avatar-anchored
 * UserMenu so the bar stays uncluttered. The legacy `navbar-locale-toggle` /
 * `navbar-theme-toggle` / `navbar-logout` testids are intentionally retired.
 *
 * Session gate behaviour is unchanged from slice-1 (redirect to /login when
 * no session). We keep the loading + null branches identical so existing
 * e2e selectors continue to resolve.
 */
export function ProtectedShell({ children, fullBleed = false }: ProtectedShellProps) {
  const { t } = useTranslation();
  const { data: session, isPending } = authClient.useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isPending && !session) {
      navigate({ to: "/login", replace: true });
    }
  }, [session, isPending, navigate]);

  if (isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-(--color-background) text-sm text-(--color-muted-foreground)">
        {t("common.loading")}
      </div>
    );
  }
  if (!session) return null;

  const displayName = session.user.name ?? session.user.email;
  const image = (session.user as { image?: string | null }).image;

  return (
    <div className="relative flex min-h-dvh flex-col bg-(--color-background)">
      <header
        data-testid="navbar"
        className="sticky top-0 z-30 flex h-14 shrink-0 items-center border-b border-(--color-border) bg-(--color-card)/95 backdrop-blur supports-[backdrop-filter]:bg-(--color-card)/85"
      >
        <div
          data-testid="navbar-inner"
          className="mx-auto grid w-full max-w-[1600px] items-center px-6"
          style={{ gridTemplateColumns: "1fr auto 1fr" }}
        >
          <Link
            to="/"
            className="flex items-center gap-2.5 text-sm font-semibold tracking-tight text-(--color-foreground)"
          >
            <img src="/logo.png" alt="" aria-hidden className="size-7 object-contain" />
            {t("auth.home.topNavTitle")}
          </Link>
          {/* Active link uses the Aura primary tint instead of the prior
              muted-gray bg which read as "disabled". */}
          <nav className="hidden items-center justify-center gap-1 sm:flex">
            <Link
              to="/meetings"
              data-testid="navbar-meetings-link"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-(--color-muted-foreground) transition-colors hover:bg-(--color-primary-soft) hover:text-(--color-foreground)"
              activeProps={{
                className: "bg-(--color-primary-soft) text-(--color-primary)",
              }}
            >
              {t("nav.meetings")}
            </Link>
            <Link
              to="/recordings"
              data-testid="navbar-recordings-link"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-(--color-muted-foreground) transition-colors hover:bg-(--color-primary-soft) hover:text-(--color-foreground)"
              activeProps={{
                className: "bg-(--color-primary-soft) text-(--color-primary)",
              }}
            >
              {t("nav.recordings")}
            </Link>
            <Link
              to="/dashboard"
              data-testid="navbar-dashboard-link"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-(--color-muted-foreground) transition-colors hover:bg-(--color-primary-soft) hover:text-(--color-foreground)"
              activeProps={{
                className: "bg-(--color-primary-soft) text-(--color-primary)",
              }}
            >
              {t("nav.dashboard")}
            </Link>
          </nav>
          <div className="flex items-center justify-end gap-1">
            <LocaleToggle />
            <ThemeToggle />
            <span className="mx-1.5 h-5 w-px bg-(--color-border)" aria-hidden />
            <UserMenu displayName={displayName ?? "?"} image={image} />
          </div>
        </div>
      </header>
      <main
        data-testid="protected-shell-main"
        className={
          fullBleed
            ? "flex-1 space-y-6 px-6 py-6"
            : "mx-auto w-full max-w-[1600px] flex-1 space-y-6 px-6 py-10"
        }
      >
        {children}
      </main>
    </div>
  );
}
