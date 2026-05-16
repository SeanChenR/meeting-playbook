/**
 * /settings/profile — slice-19 polish, Sean review round 2.
 *
 * Two equal-height profile cards arranged in a `auto-rows-fr` grid:
 *
 *   1. Identity — large centered avatar + display name + email
 *   2. Account  — linked-provider stack + verification + member-since
 *
 * Each card uses:
 *   - `<GradientCardFrame>` — gradient border + subtle radial bg, both
 *     intensify on hover (Sean review round 4)
 *   - `animate-ui` icon header that animates on hover
 *
 * No BorderBeam (the rotating line was retired per Sean's feedback). The
 * gradient border supplies the "line accent on the edge" he asked for.
 */

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Mail } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Lock } from "../../components/animate-ui/icons/lock";
import { Sparkles } from "../../components/animate-ui/icons/sparkles";
import { GradientCardFrame } from "../../components/magicui/gradient-card-frame";
import { Avatar } from "../../components/ui/avatar";
import { Badge } from "../../components/ui/badge";
import { authClient } from "../../lib/auth-client";

interface LinkedAccount {
  providerId: string;
  createdAt?: string;
}

async function _fetchLinkedAccounts(): Promise<LinkedAccount[]> {
  const result = await authClient.listAccounts();
  return ((result as { data?: LinkedAccount[] }).data ?? []) as LinkedAccount[];
}

function _formatDate(iso: string | undefined, locale: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" });
}

export function SettingsProfile() {
  const { t, i18n } = useTranslation();
  const { data: session } = authClient.useSession();
  const accountsQuery = useQuery({
    queryKey: ["auth-accounts"],
    queryFn: _fetchLinkedAccounts,
    staleTime: Infinity,
    enabled: !!session,
  });

  const user = session?.user;
  const displayName = user?.name ?? user?.email ?? "";
  const image = (user as { image?: string | null } | undefined)?.image;
  const emailVerified = (user as { emailVerified?: boolean } | undefined)?.emailVerified;

  const accounts = accountsQuery.data ?? [];
  const hasGoogle = accounts.some((a) => a.providerId === "google");
  const hasCredential = accounts.some((a) => a.providerId === "credential");
  const memberSince = accounts.reduce<string | undefined>((earliest, a) => {
    if (!a.createdAt) return earliest;
    if (!earliest) return a.createdAt;
    return a.createdAt < earliest ? a.createdAt : earliest;
  }, undefined);

  return (
    <div className="grid auto-rows-fr grid-cols-1 gap-4 md:grid-cols-2">
      {/* ─── Identity card ───────────────────────────────────────────── */}
      <GradientCardFrame
        data-testid="settings-profile-identity"
        accent="var(--color-primary)"
        accentAlt="var(--color-accent)"
        className="h-full"
        bodyClassName="h-full"
      >
        <div className="flex h-full flex-col rounded-[inherit] p-6">
          <header className="flex items-center gap-2">
            <Sparkles animate="hover" animateOnHover className="size-4 text-(--color-primary)" />
            <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
              {t("settings.profile.title")}
            </h2>
          </header>

          <div className="flex flex-1 flex-col items-center justify-center gap-4 py-8 text-center">
            <Avatar
              src={image}
              alt={displayName}
              fallback={displayName[0] ?? "?"}
              className="size-24 text-2xl ring-2 ring-(--color-primary)/30 ring-offset-2 ring-offset-(--color-card)"
              data-testid="settings-profile-avatar"
            />
            <div className="space-y-1">
              <p
                data-testid="settings-profile-name"
                className="text-xl font-semibold tracking-tight text-(--color-foreground)"
              >
                {user?.name ?? "—"}
              </p>
              <p
                data-testid="settings-profile-email"
                className="flex items-center justify-center gap-1.5 text-sm text-(--color-muted-foreground)"
              >
                {user?.email ?? "—"}
                {emailVerified && (
                  <CheckCircle2
                    className="size-3.5 text-(--color-accent)"
                    aria-label={t("settings.profile.verifiedLabel")}
                  />
                )}
              </p>
            </div>
          </div>

          <p className="text-center text-xs text-(--color-muted-foreground)">
            {t("settings.profile.subhead")}
          </p>
        </div>
      </GradientCardFrame>

      {/* ─── Account card ────────────────────────────────────────────── */}
      <GradientCardFrame
        data-testid="settings-profile-account"
        accent="var(--color-accent)"
        accentAlt="var(--color-primary)"
        className="h-full"
        bodyClassName="h-full"
      >
        <div className="flex h-full flex-col rounded-[inherit] p-6">
          <header className="flex items-center justify-center gap-2">
            <Lock animate="hover" animateOnHover className="size-4 text-(--color-accent)" />
            <h2 className="text-sm font-semibold tracking-tight text-(--color-foreground)">
              {t("settings.profile.accountTitle")}
            </h2>
          </header>

          <div className="mt-6 flex flex-1 flex-col items-center justify-center gap-6 text-center">
            <section className="space-y-3">
              <p className="text-xs uppercase tracking-wide text-(--color-muted-foreground)">
                {t("settings.profile.providerLabel")}
              </p>
              <div className="flex flex-wrap items-center justify-center gap-3">
                {hasCredential && (
                  <_ProviderTile
                    testId="settings-profile-provider-credential"
                    icon={<Mail className="size-9 text-(--color-primary)" />}
                    label={t("settings.profile.providerCredential")}
                  />
                )}
                {hasGoogle && (
                  <_ProviderTile
                    testId="settings-profile-provider-google"
                    icon={<_GoogleGlyph className="size-9" />}
                    label="Google"
                  />
                )}
                {accounts.length === 0 && (
                  <span className="text-xs text-(--color-muted-foreground)">—</span>
                )}
              </div>
            </section>

            <section className="space-y-2">
              <p className="text-xs uppercase tracking-wide text-(--color-muted-foreground)">
                {t("settings.profile.verificationLabel")}
              </p>
              {emailVerified ? (
                <Badge
                  data-testid="settings-profile-verified-badge"
                  variant="success"
                  className="gap-1.5"
                >
                  <CheckCircle2 className="size-3.5" />
                  {t("settings.profile.verifiedYes")}
                </Badge>
              ) : (
                <Badge variant="outline">{t("settings.profile.verifiedNo")}</Badge>
              )}
            </section>
          </div>

          <footer className="mt-6 flex items-baseline justify-center gap-3 border-t border-(--color-border)/60 pt-4 text-center">
            <span className="text-xs uppercase tracking-wide text-(--color-muted-foreground)">
              {t("settings.profile.memberSinceLabel")}
            </span>
            <span
              data-testid="settings-profile-member-since"
              className="text-sm font-medium text-(--color-foreground)"
            >
              {_formatDate(memberSince, i18n.language)}
            </span>
          </footer>
        </div>
      </GradientCardFrame>
    </div>
  );
}

function _ProviderTile({
  testId,
  icon,
  label,
}: {
  testId: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <div
      data-testid={testId}
      className="flex flex-col items-center gap-2 rounded-lg border border-(--color-border) bg-(--color-card) px-5 py-4 text-sm font-medium text-(--color-foreground) shadow-sm transition-colors hover:bg-(--color-muted)"
    >
      {icon}
      <span>{label}</span>
    </div>
  );
}

function _GoogleGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.07 5.07 0 0 1-2.2 3.32v2.76h3.56c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.56-2.76c-.99.66-2.25 1.05-3.72 1.05-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.43.34-2.1V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.93l3.66-2.83z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.65l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.66 2.83C6.71 7.31 9.14 5.38 12 5.38z"
      />
    </svg>
  );
}
