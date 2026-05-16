/**
 * /settings/security — slice-19 polish, Sean review round 2.
 *
 * Single centered card surfacing 2FA status + enrollment CTA. Matches
 * the profile-page treatment: GradientCardFrame (hover bg/border intensify)
 * + animate-ui Lock icon header, content vertically centered.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Lock } from "../../components/animate-ui/icons/lock";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";
import { Badge } from "../../components/ui/badge";
import { buttonVariants } from "../../components/ui/button";
import { authClient } from "../../lib/auth-client";

interface LinkedAccount {
  providerId: string;
}

async function _fetchHasCredential(): Promise<boolean> {
  const result = await authClient.listAccounts();
  const accounts = ((result as { data?: LinkedAccount[] }).data ?? []) as LinkedAccount[];
  return accounts.some((a) => a.providerId === "credential");
}

export function SettingsSecurity() {
  const { t } = useTranslation();
  const { data: session } = authClient.useSession();
  const accountsQuery = useQuery({
    queryKey: ["auth-accounts"],
    queryFn: _fetchHasCredential,
    staleTime: Infinity,
    enabled: !!session,
  });

  const user = session?.user as { twoFactorEnabled?: boolean } | undefined;
  const twoFactorEnabled = user?.twoFactorEnabled === true;
  const hasCredential = accountsQuery.data ?? false;

  return (
    <GradientCardFrame
      data-testid="settings-security"
      accent="var(--color-primary)"
      accentAlt="var(--color-accent)"
    >
      <div className="flex flex-col rounded-[inherit] p-8">
        <header className="flex items-center justify-center gap-2">
          <Lock animate="hover" animateOnHover className="size-4 text-(--color-primary)" />
          <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
            {t("settings.security.title")}
          </h2>
        </header>

        <div className="flex flex-col items-center gap-6 py-10 text-center">
          <div className="relative">
            <div
              className={
                twoFactorEnabled
                  ? "flex size-20 items-center justify-center rounded-full bg-(--color-accent)/15 ring-2 ring-(--color-accent)/40"
                  : "flex size-20 items-center justify-center rounded-full bg-(--color-card) ring-2 ring-(--color-primary)/40"
              }
            >
              {twoFactorEnabled ? (
                <ShieldCheck className="size-10 text-(--color-accent)" aria-hidden />
              ) : (
                <img src="/icons/google-authenticator.png" alt="" aria-hidden className="size-12" />
              )}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-base font-semibold text-(--color-foreground)">
              {twoFactorEnabled
                ? t("settings.security.enabledTitle")
                : t("settings.security.title")}
            </p>
            <p className="max-w-md text-sm text-(--color-muted-foreground)">
              {twoFactorEnabled ? t("settings.security.enabledBody") : t("settings.security.intro")}
            </p>
          </div>

          <Badge
            data-testid="settings-security-status-badge"
            variant={twoFactorEnabled ? "success" : "outline"}
            className="gap-1.5"
          >
            {twoFactorEnabled ? (
              <ShieldCheck className="size-3.5" />
            ) : (
              <Lock className="size-3.5" />
            )}
            {twoFactorEnabled
              ? t("settings.security.statusEnabled")
              : t("settings.security.statusDisabled")}
          </Badge>

          {!twoFactorEnabled && hasCredential && (
            <Link
              to="/totp/enroll"
              data-testid="settings-security-enroll-cta"
              className={buttonVariants({ variant: "primary" })}
            >
              {t("settings.security.enroll")}
            </Link>
          )}

          {!hasCredential && (
            <p
              data-testid="settings-security-oauth-note"
              className="max-w-md text-xs text-(--color-muted-foreground)"
            >
              {t("settings.security.oauthOnlyHint")}
            </p>
          )}
        </div>
      </div>
    </GradientCardFrame>
  );
}
