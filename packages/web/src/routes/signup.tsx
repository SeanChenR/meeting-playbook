/**
 * Signup route — slice ui-overhaul-claude-design task 3.2.
 *
 * Visual contract aligned with design bundle `SignupScreen`:
 *   - 360px width card centered inside AuthShell
 *   - Headline + subhead inside the card
 *   - Display name + Email + Password fields with hint text
 *   - Primary "建立帳號" button (full width)
 *   - Bottom "已有帳號？登入" link
 *
 * Confirm-password field retained for parity with the existing test
 * contract (signup.test.tsx asserts /confirm password/i label and the
 * mismatch / too-short error guards). Design bundle omits it; production
 * keeps the safety net.
 *
 * Preserves existing i18n keys and Better Auth signUp.email behavior.
 */

import { Loader } from "../components/animate-ui/icons/loader";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "@tanstack/react-router";
import { AuthShell } from "../components/auth-shell";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { authClient } from "../lib/auth-client";

export function Signup() {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError(t("auth.signup.mismatchError"));
      return;
    }
    if (password.length < 8) {
      setError(t("auth.signup.tooShortError"));
      return;
    }

    setSubmitting(true);
    try {
      const result = await authClient.signUp.email({ email, password, name });
      const r = result as { error?: { message?: string } };
      if (r.error) {
        setError(r.error.message ?? t("auth.signup.errorFallback"));
        setSubmitting(false);
        return;
      }
      navigate({ to: "/meetings", replace: true });
    } catch (e) {
      setError(`${t("auth.signup.errorFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <Card className="mx-auto w-[360px]">
        <CardContent className="space-y-5 p-6">
          <div className="space-y-1 text-center">
            <h1 className="text-xl font-semibold tracking-tight text-(--color-foreground)">
              {t("auth.signup.title")}
            </h1>
            <p className="text-sm text-(--color-muted-foreground)">{t("auth.signup.subtitle")}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="signup-name">{t("auth.signup.nameLabel")}</Label>
              <Input
                id="signup-name"
                type="text"
                autoComplete="name"
                placeholder={t("auth.signup.namePlaceholder")}
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="signup-email">{t("auth.signup.emailLabel")}</Label>
              <Input
                id="signup-email"
                type="email"
                autoComplete="email"
                placeholder={t("auth.signup.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <Label htmlFor="signup-password">{t("auth.signup.passwordLabel")}</Label>
                <span className="text-xs text-(--color-muted-foreground)">
                  {t("auth.signup.passwordHint")}
                </span>
              </div>
              <Input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                placeholder={t("auth.signup.passwordPlaceholder")}
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="signup-confirm">{t("auth.signup.confirmLabel")}</Label>
              <Input
                id="signup-confirm"
                type="password"
                autoComplete="new-password"
                placeholder={t("auth.signup.confirmPlaceholder")}
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting && <Loader animate="spin" className="size-4" />}
              {submitting ? t("auth.signup.submitting") : t("auth.signup.submit")}
            </Button>
          </form>

          {error && (
            <Alert variant="destructive" data-testid="signup-error">
              {error}
            </Alert>
          )}

          <p className="text-center text-sm text-(--color-muted-foreground)">
            {t("auth.signup.alreadyHaveAccount")}{" "}
            <Link
              to="/login"
              className="font-medium text-(--color-primary) underline-offset-4 hover:underline"
            >
              {t("auth.signup.loginLink")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
