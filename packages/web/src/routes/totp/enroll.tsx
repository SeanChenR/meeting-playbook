import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "@tanstack/react-router";
import { QRCodeSVG } from "qrcode.react";
import { AuthShell } from "../../components/auth-shell";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Separator } from "../../components/ui/separator";
import { authClient } from "../../lib/auth-client";

type EnrollData = { totpURI: string; backupCodes: string[] };

export function TotpEnroll() {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [enrollData, setEnrollData] = useState<EnrollData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleEnableSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.twoFactor.enable({ password });
      const r = result as { data?: EnrollData; error?: { message?: string } };
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

  if (!enrollData) {
    return (
      <AuthShell eyebrow={t("auth.totp.enroll.eyebrowStep1")}>
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <span className="rounded-md bg-(--color-muted) p-2">
                <KeyRound className="size-4" />
              </span>
              <CardTitle className="text-lg">{t("auth.totp.enroll.step1Title")}</CardTitle>
            </div>
            <CardDescription>{t("auth.totp.enroll.step1Description")}</CardDescription>
          </CardHeader>
          <CardContent>
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
              <Alert variant="destructive" className="mt-4" data-testid="totp-error">
                {error}
              </Alert>
            )}
          </CardContent>
        </Card>
      </AuthShell>
    );
  }

  return (
    <AuthShell eyebrow={t("auth.totp.enroll.eyebrowStep2")}>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-(--color-accent)/12 p-2 text-(--color-accent)">
              <ShieldCheck className="size-4" />
            </span>
            <CardTitle className="text-lg">{t("auth.totp.enroll.step2Title")}</CardTitle>
          </div>
          <CardDescription>{t("auth.totp.enroll.step2Description")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex justify-center rounded-md border border-(--color-border) bg-(--color-card) p-4">
            <QRCodeSVG value={enrollData.totpURI} size={192} />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">{t("auth.totp.enroll.backupCodesTitle")}</p>
            <p className="text-xs text-(--color-muted-foreground)">
              {t("auth.totp.enroll.backupCodesHelp")}
            </p>
            <ul
              data-testid="backup-codes"
              className="grid grid-cols-2 gap-2 rounded-md border border-(--color-border) bg-(--color-muted)/40 p-3"
            >
              {enrollData.backupCodes.map((c) => (
                <li key={c}>
                  <code className="font-mono text-xs text-(--color-foreground)">{c}</code>
                </li>
              ))}
            </ul>
          </div>

          <Separator />

          <form onSubmit={handleVerifySubmit} className="space-y-4">
            <div className="space-y-1.5">
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
                className="font-mono tracking-[0.4em] text-center text-base"
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting
                ? t("auth.totp.enroll.verifySubmitting")
                : t("auth.totp.enroll.verifyButton")}
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
