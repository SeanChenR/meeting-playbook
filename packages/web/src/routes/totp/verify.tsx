import { ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "@tanstack/react-router";
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
    <AuthShell eyebrow={t("auth.totp.verify.eyebrow")}>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-(--color-muted) p-2">
              <ShieldCheck className="size-4" />
            </span>
            <CardTitle className="text-lg">{t("auth.totp.verify.title")}</CardTitle>
          </div>
          <CardDescription>{t("auth.totp.verify.description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
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
                className="font-mono tracking-[0.4em] text-center text-base"
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? t("auth.totp.verify.submitting") : t("auth.totp.verify.submit")}
            </Button>
          </form>
          {error && (
            <Alert variant="destructive" className="mt-4" data-testid="totp-verify-error">
              {error}
            </Alert>
          )}
        </CardContent>
      </Card>
    </AuthShell>
  );
}
