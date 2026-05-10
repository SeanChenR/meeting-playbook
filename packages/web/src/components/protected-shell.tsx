import { LogOut } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "@tanstack/react-router";
import { authClient } from "../lib/auth-client";
import { Avatar } from "./ui/avatar";
import { Button } from "./ui/button";
import { LocaleToggle } from "./locale-toggle";

export interface ProtectedShellProps {
  children: ReactNode;
  /**
   * Slice-07: when true, the main content area drops its centered max-width
   * container so the page can use the full viewport width. Default false
   * preserves the existing centered layout for list / new / login / etc.
   * The detail page passes `fullBleed` so its 3-column / stack workspace
   * isn't squashed into a 1200px column.
   */
  fullBleed?: boolean;
}

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
    <div className="min-h-dvh bg-(--color-background)">
      <header className="border-b border-(--color-border) bg-(--color-card)">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-5">
          <Link to="/meetings" className="text-sm font-semibold tracking-tight">
            {t("auth.home.topNavTitle")}
          </Link>
          <div className="flex items-center gap-3">
            <LocaleToggle />
            <Avatar
              src={image}
              alt={displayName}
              fallback={displayName?.[0] ?? "?"}
              data-testid="user-avatar"
            />
            <Button type="button" variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="size-4" />
              {t("auth.home.logout")}
            </Button>
          </div>
        </div>
      </header>
      <main
        data-testid="protected-shell-main"
        className={
          fullBleed ? "space-y-6 px-5 py-6" : "mx-auto max-w-[1200px] space-y-6 px-5 py-10"
        }
      >
        {children}
      </main>
    </div>
  );
}
