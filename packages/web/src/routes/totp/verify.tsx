/**
 * TotpVerify route — slice ui-overhaul-claude-design task 3.4.
 *
 * Visual contract aligned with design bundle `TotpVerifyScreen`:
 *   - 380px width card centered inside AuthShell
 *   - Lock icon hero in primary-soft circle
 *   - Headline + subhead
 *   - 6-digit input slot with "30s refresh" hint
 *   - Primary "驗證" button
 *   - "使用備用碼登入" link below
 *
 * Preserves Better Auth `verifyTotp` flow + i18n keys + the 6-digit input
 * label that the existing tests use to query (`/驗證碼/`).
 */

import { Lock } from "../../components/animate-ui/icons/lock";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "@tanstack/react-router";
import { AuthShell } from "../../components/auth-shell";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { authClient } from "../../lib/auth-client";

export function TotpVerify() {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.twoFactor.verifyTotp({ code });
      const r = result as { data?: unknown; error?: { message?: string } | null };
      if (r.error) {
        setError(r.error.message ?? t("auth.totp.verify.errorFallback"));
        setSubmitting(false);
        return;
      }
      await authClient.getSession();
      navigate({ to: "/meetings", replace: true });
    } catch (e) {
      setError(`${t("auth.totp.verify.errorFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <Card className="mx-auto w-[380px]">
        <CardContent className="space-y-5 p-6">
          <div className="space-y-3 text-center">
            <div className="mx-auto inline-flex rounded-full bg-(--color-primary)/12 p-2.5">
              <Lock animateOnHover className="size-5 text-(--color-primary)" />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
                {t("auth.totp.verify.title")}
              </h1>
              <p className="text-sm text-(--color-muted-foreground)">
                {t("auth.totp.verify.description")}
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="totp-verify-code">{t("auth.totp.verify.codeLabel")}</Label>
              <Input
                id="totp-verify-code"
                name="code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                placeholder={t("auth.totp.verify.codePlaceholder")}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoFocus
                className="text-center font-mono text-base tracking-[0.4em]"
              />
              <p className="text-center text-xs text-(--color-muted-foreground)">
                {t("auth.totp.verify.refreshHint")}
              </p>
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? t("auth.totp.verify.submitting") : t("auth.totp.verify.submit")}
            </Button>
          </form>

          {error && (
            <Alert variant="destructive" data-testid="totp-verify-error">
              {error}
            </Alert>
          )}

          <p className="text-center text-sm">
            <a
              href="#backup"
              className="font-medium text-(--color-primary) underline-offset-4 hover:underline"
            >
              {t("auth.totp.verify.useBackupCode")}
            </a>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
