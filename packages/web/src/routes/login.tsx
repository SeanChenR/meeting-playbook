import { Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { AuthShell } from "../components/auth-shell";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Separator } from "../components/ui/separator";
import { authClient } from "../lib/auth-client";
import { localizedErrorMessage } from "../lib/i18n-errors";

export function Login() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/meetings",
    });
  };

  const handleEmailSignIn = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.signIn.email({ email, password });
      const r = result as {
        error?: { error_code?: string; message?: string };
        data?: { twoFactorRedirect?: boolean };
      };
      if (r.error) {
        const localized = r.error.error_code
          ? localizedErrorMessage(r.error.error_code, t)
          : (r.error.message ?? t("auth.login.errorFallback"));
        setError(localized);
        setSubmitting(false);
        return;
      }
      if (r.data?.twoFactorRedirect) {
        navigate("/totp/verify", { replace: true });
        return;
      }
      navigate("/meetings", { replace: true });
    } catch (e) {
      setError(`${t("auth.login.errorFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow={t("auth.login.eyebrow")}>
      <Card>
        <CardHeader>
          <CardTitle>{t("auth.login.title")}</CardTitle>
          <CardDescription>{t("auth.login.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={handleGoogleSignIn}
            className="w-full"
          >
            <GoogleIcon />
            {t("auth.login.googleButton")}
          </Button>

          <div className="relative flex items-center gap-3">
            <Separator className="flex-1" />
            <span className="text-xs uppercase tracking-wider text-(--color-muted-foreground)">
              {t("auth.login.separator")}
            </span>
            <Separator className="flex-1" />
          </div>

          <form onSubmit={handleEmailSignIn} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="login-email">{t("auth.login.emailLabel")}</Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                placeholder={t("auth.login.emailPlaceholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="login-password">{t("auth.login.passwordLabel")}</Label>
              <Input
                id="login-password"
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
              {submitting ? t("auth.login.submitting") : t("auth.login.submit")}
            </Button>
          </form>

          {error && (
            <Alert variant="destructive" data-testid="login-error">
              {error}
            </Alert>
          )}

          <p className="text-center text-sm text-(--color-muted-foreground)">
            {t("auth.login.noAccount")}{" "}
            <Link
              to="/signup"
              className="font-medium text-(--color-foreground) underline-offset-4 hover:underline"
            >
              {t("auth.login.signupLink")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}

/** Inline Google "G" mark — avoids pulling a logo lib for one icon. */
function GoogleIcon() {
  return (
    <svg aria-hidden className="size-4" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.92v2.32A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.96H.92A9 9 0 0 0 0 9c0 1.45.35 2.82.92 4.04l3.05-2.32Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.34l2.58-2.58A8.97 8.97 0 0 0 9 0 9 9 0 0 0 .92 4.96l3.05 2.32C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}
