/**
 * TotpEnroll route — slice ui-overhaul-claude-design task 3.3.
 *
 * Visual contract aligned with design bundle `TotpEnrollScreen`:
 *   step 1 (password gate) — single 360px card; preserves the
 *           confirm-password gate before calling twoFactor.enable.
 *   step 2 (QR + verify)  — 420px card; Shield icon hero; real QR code;
 *           secret code mono row with copy button; 6-digit input slot;
 *           separator; backup codes grid + download button + verify button.
 *
 * Preserves the two-step flow + i18n keys + Better Auth contract. The
 * design bundle shows step 2 only — step 1 stays because it is required
 * by the auth flow and asserted by enroll.test.tsx.
 */

import { Copy, Download, Loader2, Shield, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "@tanstack/react-router";
import { QRCodeSVG } from "qrcode.react";
import { AuthShell } from "../../components/auth-shell";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Separator } from "../../components/ui/separator";
import { authClient } from "../../lib/auth-client";

type EnrollData = { totpURI: string; backupCodes: string[] };

function _extractSecret(uri: string): string {
  const match = /[?&]secret=([^&]+)/i.exec(uri);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

export function TotpEnroll() {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [enrollData, setEnrollData] = useState<EnrollData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  const handleEnableSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.twoFactor.enable({ password });
      const r = result as unknown as { data?: EnrollData; error?: { message?: string } };
      if (r.error) {
        setError(r.error.message ?? t("auth.totp.enroll.enableErrorFallback"));
        setSubmitting(false);
        return;
      }
      if (r.data) setEnrollData(r.data);
      setSubmitting(false);
    } catch (e) {
      setError(`${t("auth.totp.enroll.enableErrorFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  const handleVerifySubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.twoFactor.verifyTotp({ code });
      const r = result as { data?: unknown; error?: { message?: string } | null };
      if (r.error) {
        setError(r.error.message ?? t("auth.totp.enroll.codeRejectedFallback"));
        setSubmitting(false);
        return;
      }
      await authClient.getSession();
      navigate({ to: "/meetings", replace: true });
    } catch (e) {
      setError(`${t("auth.totp.enroll.codeRejectedFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  const handleCopySecret = async (secret: string) => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard write may be blocked; silently ignore — UI shows no error.
    }
  };

  const handleDownloadBackupCodes = (codes: string[]) => {
    const blob = new Blob([codes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "meeting-playbook-backup-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!enrollData) {
    return (
      <AuthShell>
        <Card className="mx-auto w-[360px]">
          <CardContent className="space-y-5 p-6">
            <div className="space-y-3 text-center">
              <div className="mx-auto inline-flex rounded-full bg-(--color-primary)/12 p-2.5">
                <Shield className="size-5 text-(--color-primary)" />
              </div>
              <div className="space-y-1">
                <h1 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
                  {t("auth.totp.enroll.step1Title")}
                </h1>
                <p className="mx-auto max-w-[280px] text-sm text-(--color-muted-foreground)">
                  {t("auth.totp.enroll.step1Description")}
                </p>
              </div>
            </div>

            <form onSubmit={handleEnableSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="enroll-password">{t("auth.totp.enroll.passwordLabel")}</Label>
                <Input
                  id="enroll-password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting && <Loader2 className="size-4 animate-spin" />}
                {submitting
                  ? t("auth.totp.enroll.continueSubmitting")
                  : t("auth.totp.enroll.continueButton")}
              </Button>
            </form>
            {error && (
              <Alert variant="destructive" data-testid="totp-error">
                {error}
              </Alert>
            )}
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  const secret = _extractSecret(enrollData.totpURI);

  return (
    <AuthShell>
      <Card className="mx-auto w-[420px]">
        <CardContent className="space-y-4 p-6">
          <div className="space-y-3 text-center">
            <div className="mx-auto inline-flex rounded-full bg-(--color-primary)/12 p-2.5">
              <ShieldCheck className="size-5 text-(--color-primary)" />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
                {t("auth.totp.enroll.step2Title")}
              </h1>
              <p className="mx-auto max-w-[300px] text-sm text-(--color-muted-foreground)">
                {t("auth.totp.enroll.step2Description")}
              </p>
            </div>
          </div>

          <div className="flex justify-center">
            <div className="rounded-md border border-(--color-border) bg-white p-3">
              <QRCodeSVG value={enrollData.totpURI} size={168} />
            </div>
          </div>

          {secret && (
            <div className="flex items-center justify-between gap-3 rounded-md bg-(--color-muted)/50 px-3 py-2">
              <code className="truncate font-mono text-xs text-(--color-muted-foreground)">
                {secret}
              </code>
              <button
                type="button"
                data-testid="copy-secret"
                aria-label={t("auth.totp.enroll.copySecret")}
                title={t("auth.totp.enroll.copySecret")}
                onClick={() => handleCopySecret(secret)}
                className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-(--color-muted-foreground) hover:bg-(--color-muted) hover:text-(--color-foreground)"
              >
                <Copy className="size-3.5" />
              </button>
            </div>
          )}

          <form onSubmit={handleVerifySubmit} className="space-y-3">
            <Label htmlFor="totp-code">{t("auth.totp.enroll.codeLabel")}</Label>
            <Input
              id="totp-code"
              name="code"
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              autoComplete="one-time-code"
              placeholder={t("auth.totp.enroll.codePlaceholder")}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              className="text-center font-mono text-base tracking-[0.4em]"
            />
          </form>

          <Separator />

          <div className="space-y-2">
            <p className="text-sm font-semibold text-(--color-foreground)">
              {t("auth.totp.enroll.backupCodesTitle")}
            </p>
            <p className="text-xs text-(--color-muted-foreground)">
              {t("auth.totp.enroll.backupCodesHelp")}
            </p>
            <ul
              data-testid="backup-codes"
              className="grid grid-cols-2 gap-1.5 rounded-md bg-(--color-muted)/50 p-2.5"
            >
              {enrollData.backupCodes.map((c) => (
                <li key={c}>
                  <code className="font-mono text-xs text-(--color-foreground)">{c}</code>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => handleDownloadBackupCodes(enrollData.backupCodes)}
              data-testid="download-backup-codes"
            >
              <Download className="size-3.5" />
              {t("auth.totp.enroll.downloadBackupCodes")}
            </Button>
            <div className="flex-1" />
            <Button
              type="button"
              size="sm"
              disabled={submitting}
              onClick={(e) => handleVerifySubmit(e as unknown as FormEvent<HTMLFormElement>)}
            >
              {submitting && <Loader2 className="size-3.5 animate-spin" />}
              {submitting
                ? t("auth.totp.enroll.verifySubmitting")
                : t("auth.totp.enroll.verifyButton")}
            </Button>
          </div>

          {copied && (
            <p className="text-center text-xs text-(--color-success)" role="status">
              {t("auth.totp.enroll.copiedTooltip")}
            </p>
          )}
          {error && (
            <Alert variant="destructive" data-testid="totp-error">
              {error}
            </Alert>
          )}
        </CardContent>
      </Card>
    </AuthShell>
  );
}
