import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ExternalLink, LogOut, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { LocaleToggle } from "../components/locale-toggle";
import { Avatar } from "../components/ui/avatar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Separator } from "../components/ui/separator";
import { authClient } from "../lib/auth-client";

type ApiMeResponse = { user_id: string };
type LinkedAccount = { providerId: string };

async function fetchMe(): Promise<ApiMeResponse> {
  const r = await fetch("/api/me");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as ApiMeResponse;
}

async function fetchHasCredential(): Promise<boolean> {
  const result = await authClient.listAccounts();
  const accounts = ((result as { data?: LinkedAccount[] }).data ?? []) as LinkedAccount[];
  return accounts.some((a) => a.providerId === "credential");
}

export function Home() {
  const { t } = useTranslation();
  const { data: session, isPending } = authClient.useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isPending && !session) {
      navigate({ to: "/login", replace: true });
    }
  }, [session, isPending, navigate]);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    enabled: !!session,
  });
  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: fetchHasCredential,
    enabled: !!session,
  });

  const backendUserId = meQuery.data?.user_id ?? null;
  const backendError = meQuery.error ? String(meQuery.error) : null;
  const hasCredential = accountsQuery.isSuccess
    ? accountsQuery.data
    : accountsQuery.isError
      ? false
      : null;

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

  const twoFactorEnabled = (session.user as { twoFactorEnabled?: boolean }).twoFactorEnabled;
  const displayName = session.user.name ?? session.user.email;

  return (
    <div className="min-h-dvh bg-(--color-background)">
      <header className="border-b border-(--color-border) bg-(--color-card)">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-5">
          <span className="text-sm font-semibold tracking-tight">{t("auth.home.topNavTitle")}</span>
          <div className="flex items-center gap-3">
            <LocaleToggle />
            <Avatar
              src={(session.user as { image?: string | null }).image}
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

      <main className="mx-auto max-w-[1200px] space-y-6 px-5 py-10">
        <Card>
          <CardHeader>
            <CardDescription>{t("auth.home.greetingEyebrow")}</CardDescription>
            <CardTitle className="text-3xl">
              {t("auth.home.greetingTitle", { name: displayName })}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {backendUserId && (
              <div
                data-testid="backend-confirmation"
                className="flex items-center justify-between rounded-md border border-(--color-border) bg-(--color-muted)/40 px-3 py-2"
              >
                <span className="text-xs text-(--color-muted-foreground)">
                  {t("auth.home.backendLabel")}
                </span>
                <code className="font-mono text-xs text-(--color-foreground)">{backendUserId}</code>
              </div>
            )}
            {backendError && (
              <div
                data-testid="backend-error"
                role="alert"
                className="rounded-md border border-(--color-destructive)/30 bg-(--color-destructive)/10 px-3 py-2 text-xs text-(--color-destructive)"
              >
                {t("auth.home.backendErrorPrefix")}: {backendError}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("auth.home.securityTitle")}</CardTitle>
            <CardDescription>
              {hasCredential === false
                ? t("auth.home.securityDescriptionOAuth")
                : t("auth.home.securityDescriptionCredential")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {hasCredential === null ? (
              <p className="text-sm text-(--color-muted-foreground)">
                {t("auth.home.loadingAccount")}
              </p>
            ) : hasCredential ? (
              <CredentialUserSecurity twoFactorEnabled={!!twoFactorEnabled} />
            ) : (
              <OAuthUserSecurity />
            )}
          </CardContent>
        </Card>

        <Separator />
        <p className="text-xs text-(--color-muted-foreground)">{t("auth.home.sliceFooter")}</p>
      </main>
    </div>
  );
}

function CredentialUserSecurity({ twoFactorEnabled }: { twoFactorEnabled: boolean }) {
  const { t } = useTranslation();
  if (twoFactorEnabled) {
    return (
      <div className="flex items-start gap-3" data-testid="totp-status">
        <ShieldCheck className="mt-0.5 size-5 text-(--color-accent)" />
        <div className="space-y-0.5">
          <p className="text-sm font-medium text-(--color-foreground)">
            {t("auth.home.enabledTitle")}
          </p>
          <p className="text-xs text-(--color-muted-foreground)">{t("auth.home.enabledHelp")}</p>
        </div>
        <Badge variant="success" className="ml-auto">
          {t("auth.home.enabledBadge")}
        </Badge>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <ShieldAlert className="mt-0.5 size-5 text-(--color-muted-foreground)" />
      <div className="space-y-2">
        <p className="text-sm text-(--color-foreground)">{t("auth.home.disabledTitle")}</p>
        <p className="text-xs text-(--color-muted-foreground)">{t("auth.home.disabledHelp")}</p>
        <Link to="/totp/enroll" data-testid="enable-totp-link">
          <Button type="button" variant="secondary" size="sm">
            {t("auth.home.enableButton")}
          </Button>
        </Link>
      </div>
    </div>
  );
}

function OAuthUserSecurity() {
  const { t } = useTranslation();
  return (
    <div className="flex items-start gap-3" data-testid="oauth-2fa-notice">
      <ShieldCheck className="mt-0.5 size-5 text-(--color-accent)" />
      <div className="space-y-2">
        <p className="text-sm text-(--color-foreground)">{t("auth.home.oauthNoticeTitle")}</p>
        <p className="text-xs text-(--color-muted-foreground)">{t("auth.home.oauthNoticeBody")}</p>
        <a
          href="https://myaccount.google.com/security"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-(--color-foreground) underline-offset-4 hover:underline"
          data-testid="google-security-link"
        >
          {t("auth.home.oauthSecurityLink")}
          <ExternalLink className="size-3.5" />
        </a>
      </div>
    </div>
  );
}
