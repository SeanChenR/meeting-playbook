import { ExternalLink, LogOut, ShieldAlert, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Avatar } from "../components/ui/avatar";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Separator } from "../components/ui/separator";
import { authClient } from "../lib/auth-client";

type ApiMeResponse = { user_id: string };
type LinkedAccount = { providerId: string };

export function Home() {
  const { data: session, isPending } = authClient.useSession();
  const [backendUserId, setBackendUserId] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  /** null = still loading; true = has email/password row; false = OAuth-only. */
  const [hasCredential, setHasCredential] = useState<boolean | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isPending) return;
    if (!session) {
      navigate("/login", { replace: true });
      return;
    }

    let cancelled = false;

    // Backend round-trip — proves the gateway → X-User-Id → FastAPI contract.
    (async () => {
      try {
        const r = await fetch("/api/me");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = (await r.json()) as ApiMeResponse;
        if (!cancelled) setBackendUserId(data.user_id);
      } catch (e) {
        if (!cancelled) setBackendError(String(e));
      }
    })();

    // Linked accounts — decides whether to show app-level 2FA or defer to the
    // OAuth provider's own 2FA management.
    (async () => {
      try {
        const result = await authClient.listAccounts();
        const accounts = ((result as { data?: LinkedAccount[] }).data ?? []) as LinkedAccount[];
        if (!cancelled) {
          setHasCredential(accounts.some((a) => a.providerId === "credential"));
        }
      } catch {
        if (!cancelled) setHasCredential(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, isPending, navigate]);

  const handleLogout = async () => {
    await authClient.signOut();
    navigate("/login", { replace: true });
  };

  if (isPending) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-(--color-background) text-sm text-(--color-muted-foreground)">
        Loading…
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
          <span className="text-sm font-semibold tracking-tight">Meeting Playbook</span>
          <div className="flex items-center gap-3">
            <Avatar
              src={(session.user as { image?: string | null }).image}
              alt={displayName}
              fallback={displayName?.[0] ?? "?"}
              data-testid="user-avatar"
            />
            <Button type="button" variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="size-4" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] space-y-6 px-5 py-10">
        {/* Greeting card */}
        <Card>
          <CardHeader>
            <CardDescription>已登入</CardDescription>
            <CardTitle className="text-3xl">Hello, {displayName}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {backendUserId && (
              <div
                data-testid="backend-confirmation"
                className="flex items-center justify-between rounded-md border border-(--color-border) bg-(--color-muted)/40 px-3 py-2"
              >
                <span className="text-xs text-(--color-muted-foreground)">Backend confirmed</span>
                <code className="font-mono text-xs text-(--color-foreground)">{backendUserId}</code>
              </div>
            )}
            {backendError && (
              <div
                data-testid="backend-error"
                role="alert"
                className="rounded-md border border-(--color-destructive)/30 bg-(--color-destructive)/10 px-3 py-2 text-xs text-(--color-destructive)"
              >
                Backend round-trip failed: {backendError}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Security card — different content for credential vs OAuth-only */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">帳號安全</CardTitle>
            <CardDescription>
              {hasCredential === false
                ? "你用 Google 登入。2FA 由 Google 管理"
                : "Two-factor authentication 為 email 帳號的選用功能"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {hasCredential === null ? (
              <p className="text-sm text-(--color-muted-foreground)">Loading…</p>
            ) : hasCredential ? (
              <CredentialUserSecurity twoFactorEnabled={!!twoFactorEnabled} />
            ) : (
              <OAuthUserSecurity />
            )}
          </CardContent>
        </Card>

        <Separator />
        <p className="text-xs text-(--color-muted-foreground)">
          這是 Slice 1 — 後續 slice 加入會議管理、playbook、即時轉錄等功能。
        </p>
      </main>
    </div>
  );
}

// ─── Sub-components: keeps the main render tidy ─────────────────────────────

function CredentialUserSecurity({ twoFactorEnabled }: { twoFactorEnabled: boolean }) {
  if (twoFactorEnabled) {
    return (
      <div className="flex items-start gap-3" data-testid="totp-status">
        <ShieldCheck className="mt-0.5 size-5 text-(--color-accent)" />
        <div className="space-y-0.5">
          <p className="text-sm font-medium text-(--color-foreground)">
            Two-factor authentication 已啟用
          </p>
          <p className="text-xs text-(--color-muted-foreground)">
            下次 email 登入會要求輸入 6 位數驗證碼
          </p>
        </div>
        <Badge variant="success" className="ml-auto">
          Enabled
        </Badge>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <ShieldAlert className="mt-0.5 size-5 text-(--color-muted-foreground)" />
      <div className="space-y-2">
        <p className="text-sm text-(--color-foreground)">尚未啟用 two-factor authentication</p>
        <p className="text-xs text-(--color-muted-foreground)">
          建議搭配 Authenticator app（Authy / 1Password / Google Authenticator）
        </p>
        <Link to="/totp/enroll" data-testid="enable-totp-link">
          <Button type="button" variant="secondary" size="sm">
            Enable two-factor authentication
          </Button>
        </Link>
      </div>
    </div>
  );
}

function OAuthUserSecurity() {
  return (
    <div className="flex items-start gap-3" data-testid="oauth-2fa-notice">
      <ShieldCheck className="mt-0.5 size-5 text-(--color-accent)" />
      <div className="space-y-2">
        <p className="text-sm text-(--color-foreground)">2FA 由 Google 管理</p>
        <p className="text-xs text-(--color-muted-foreground)">
          OAuth 帳號的兩階段驗證在身份提供者那邊設定，本應用不再額外加一層
        </p>
        <a
          href="https://myaccount.google.com/security"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-(--color-foreground) underline-offset-4 hover:underline"
          data-testid="google-security-link"
        >
          前往 Google 安全性設定
          <ExternalLink className="size-3.5" />
        </a>
      </div>
    </div>
  );
}
