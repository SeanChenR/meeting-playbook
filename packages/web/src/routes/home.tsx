/**
 * Home route — slice ui-overhaul-claude-design task 3.5.
 *
 * Visual contract aligned with design bundle `HomeScreen`:
 *   - Top greeting (eyebrow + headline) + date / next meeting subline
 *   - Sparkles CTA Card with "新會議" + "從 Calendar 匯入" buttons
 *   - `Alert` (warning tone) — "尚未啟用兩階段驗證" — only when the user
 *     has a credential account and 2FA is off
 *   - 3-col Stat cards (本月會議 / 平均時長 / 進行中) — empty state per
 *     Decision 7 ("Demo 資料只當設計參考、production 走空 state / API")
 *   - 最近會議 Card with empty state when no recent meetings exist
 *
 * Preserves slice-1 plumbing:
 *   - `/api/me` round-trip + `backend-confirmation` / `backend-error` testids
 *   - `enable-totp-link` (credential users with 2FA off)
 *   - `totp-status` (credential users with 2FA on)
 *   - `oauth-2fa-notice` + `google-security-link` (OAuth-only users)
 *
 * Wraps the new `ProtectedShell` for the NavBar + session gate so this
 * route no longer ships its own header.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Calendar as CalendarIcon,
  ExternalLink,
  Plus,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ProtectedShell } from "../components/protected-shell";
import { Alert } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
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
  const { t, i18n } = useTranslation();
  const { data: session } = authClient.useSession();

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

  if (!session) {
    return <ProtectedShell>{null}</ProtectedShell>;
  }

  const twoFactorEnabled = (session.user as { twoFactorEnabled?: boolean }).twoFactorEnabled;
  const displayName = session.user.name ?? session.user.email;
  const dateText = new Date().toLocaleDateString(i18n.language, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <ProtectedShell>
      <section className="space-y-1">
        <p className="text-sm text-(--color-muted-foreground)">{t("auth.home.greetingEyebrow")}</p>
        <h1 className="text-3xl font-bold tracking-tight text-(--color-foreground)">
          {t("auth.home.greetingTitle", { name: displayName })}
        </h1>
        <p className="text-sm text-(--color-muted-foreground)">{dateText}</p>
      </section>

      <Card>
        <CardContent className="flex items-start gap-4 p-6">
          <div
            aria-hidden
            className="flex size-11 shrink-0 items-center justify-center rounded-md bg-(--color-primary)/12 text-(--color-primary)"
          >
            <Sparkles className="size-5" />
          </div>
          <div className="flex-1 space-y-3">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-(--color-foreground)">
                {t("auth.home.ctaTitle")}
              </h2>
              <p className="text-sm text-(--color-muted-foreground)">
                {t("auth.home.ctaDescription")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link to="/meetings/new">
                <Button type="button" size="sm">
                  <Plus className="size-3.5" />
                  {t("auth.home.ctaNewMeeting")}
                </Button>
              </Link>
              <Link to="/calendar/import">
                <Button type="button" variant="secondary" size="sm">
                  <CalendarIcon className="size-3.5" />
                  {t("auth.home.ctaImportCalendar")}
                </Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>

      {hasCredential === true && twoFactorEnabled !== true && (
        <Alert variant="warning" data-testid="totp-warning">
          <div className="flex items-start gap-3">
            <Shield className="mt-0.5 size-4 shrink-0 text-(--color-warning)" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-semibold text-(--color-foreground)">
                {t("auth.home.totpWarningTitle")}
              </p>
              <p className="text-xs text-(--color-muted-foreground)">
                {t("auth.home.totpWarningBody")}{" "}
                <Link
                  to="/totp/enroll"
                  data-testid="enable-totp-link"
                  className="font-medium text-(--color-primary) underline-offset-4 hover:underline"
                >
                  {t("auth.home.totpWarningCta")}
                </Link>
              </p>
            </div>
          </div>
        </Alert>
      )}

      {hasCredential === true && twoFactorEnabled === true && (
        <div
          data-testid="totp-status"
          className="flex items-center gap-3 rounded-md border border-(--color-border) bg-(--color-card) p-4"
        >
          <ShieldCheck className="size-5 text-(--color-success)" />
          <div className="flex-1 space-y-0.5">
            <p className="text-sm font-medium text-(--color-foreground)">
              {t("auth.home.enabledTitle")}
            </p>
            <p className="text-xs text-(--color-muted-foreground)">{t("auth.home.enabledHelp")}</p>
          </div>
          <Badge variant="success">{t("auth.home.enabledBadge")}</Badge>
        </div>
      )}

      {hasCredential === false && (
        <div
          data-testid="oauth-2fa-notice"
          className="flex items-start gap-3 rounded-md border border-(--color-border) bg-(--color-card) p-4"
        >
          <ShieldAlert className="mt-0.5 size-5 text-(--color-muted-foreground)" />
          <div className="flex-1 space-y-2">
            <p className="text-sm text-(--color-foreground)">{t("auth.home.oauthNoticeTitle")}</p>
            <p className="text-xs text-(--color-muted-foreground)">
              {t("auth.home.oauthNoticeBody")}
            </p>
            <a
              href="https://myaccount.google.com/security"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="google-security-link"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-(--color-foreground) underline-offset-4 hover:underline"
            >
              {t("auth.home.oauthSecurityLink")}
              <ExternalLink className="size-3.5" />
            </a>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label={t("auth.home.statMonthlyMeetings")} value="—" />
        <StatCard label={t("auth.home.statAverageDuration")} value="—" />
        <StatCard label={t("auth.home.statActiveMeetings")} value="—" />
      </div>

      <Card>
        <CardContent className="p-6">
          <div className="mb-3 flex items-center">
            <p className="text-sm font-semibold text-(--color-foreground)">
              {t("auth.home.recentMeetingsTitle")}
            </p>
            <div className="flex-1" />
            <Link
              to="/meetings"
              className="text-sm font-medium text-(--color-primary) underline-offset-4 hover:underline"
            >
              {t("auth.home.recentMeetingsViewAll")}
            </Link>
          </div>
          <p className="rounded-md bg-(--color-muted)/40 px-3 py-6 text-center text-sm text-(--color-muted-foreground)">
            {t("auth.home.recentMeetingsEmpty")}
          </p>
        </CardContent>
      </Card>

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
    </ProtectedShell>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wider text-(--color-muted-foreground)">
          {label}
        </p>
        <p className="mt-2 text-2xl font-bold tracking-tight text-(--color-foreground)">{value}</p>
      </CardContent>
    </Card>
  );
}
