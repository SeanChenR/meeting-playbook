/**
 * UserMenu — slice-18 task 3.2 (Sean feedback round 2).
 *
 * Avatar-triggered dropdown that consolidates the two auxiliary controls
 * that don't fit on the NavBar bar itself: Settings (link to
 * `/settings/profile`) and Logout. Locale + Theme toggles live directly
 * on the NavBar next to the avatar (back to their pre-revision spot) so
 * they stay one click away.
 */

import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut, Settings as SettingsIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { authClient } from "../lib/auth-client";
import { Avatar } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";

interface UserMenuProps {
  displayName: string;
  image?: string | null;
}

export function UserMenu({ displayName, image }: UserMenuProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await authClient.signOut();
    navigate({ to: "/login", replace: true });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        type="button"
        data-testid="usermenu-trigger"
        aria-label={t("user_menu.trigger")}
        className="rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--color-ring)"
      >
        <Avatar
          src={image}
          alt={displayName}
          fallback={displayName?.[0] ?? "?"}
          data-testid="user-avatar"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[10rem]">
        <DropdownMenuItem asChild data-testid="usermenu-settings">
          <Link to="/settings" hash="profile" className="flex w-full items-center gap-2">
            <SettingsIcon className="size-4" aria-hidden />
            <span>{t("user_menu.settings")}</span>
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          data-testid="usermenu-logout"
          onSelect={() => {
            void handleLogout();
          }}
        >
          <LogOut className="size-4" aria-hidden />
          <span>{t("user_menu.logout")}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
