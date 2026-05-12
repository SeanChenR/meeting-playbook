import { LogOut } from "./animate-ui/icons/log-out";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "@tanstack/react-router";
import { authClient } from "../lib/auth-client";
import { LocaleToggle } from "./locale-toggle";
import { ThemeToggle } from "./theme-toggle";
import { Avatar } from "./ui/avatar";
import { Button } from "./ui/button";

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
 * ProtectedShell — slice ui-overhaul-claude-design task 2.1.
 *
 * Per `meeting-detail-layout` design Decision 1 + `ui-design-system` task
 * 2.1 acceptance criteria:
 *   - 56px sticky NavBar at top with logo (left) + locale-toggle /
 *     theme-toggle / avatar / logout (right cluster).
 *   - Main area max-width 1200px centred, OR fullBleed for detail page.
 *   - Toaster is mounted globally in App.tsx so we don't re-mount per route.
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

  const handleLogout = async () => {
    await authClient.signOut();
    navigate({ to: "/login", replace: true });
  };

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
    <div className="flex min-h-dvh flex-col bg-(--color-background)">
      <header
        data-testid="navbar"
        className="sticky top-0 z-30 flex h-14 shrink-0 items-center border-b border-(--color-border) bg-(--color-card)/95 backdrop-blur supports-[backdrop-filter]:bg-(--color-card)/85"
      >
        <div
          data-testid="navbar-inner"
          className="mx-auto flex w-full max-w-[1600px] items-center px-6"
        >
          <Link
            to="/meetings"
            className="flex items-center gap-2.5 text-sm font-semibold tracking-tight text-(--color-foreground)"
          >
            <span
              aria-hidden
              className="inline-flex size-6 items-center justify-center rounded-md bg-(--color-primary) text-(--color-primary-foreground)"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M3 7h18M3 12h12M3 17h18" />
              </svg>
            </span>
            {t("auth.home.topNavTitle")}
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <LocaleToggle />
            <ThemeToggle />
            <span className="mx-1.5 h-5 w-px bg-(--color-border)" aria-hidden />
            <Avatar
              src={image}
              alt={displayName}
              fallback={displayName?.[0] ?? "?"}
              data-testid="user-avatar"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              data-testid="logout-button"
              className="text-(--color-muted-foreground)"
            >
              <LogOut animateOnHover className="size-4" />
              <span className="sr-only sm:not-sr-only">{t("auth.home.logout")}</span>
            </Button>
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
