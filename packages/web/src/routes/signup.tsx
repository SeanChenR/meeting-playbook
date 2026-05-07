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
      navigate("/meetings", { replace: true });
    } catch (e) {
      setError(`${t("auth.signup.errorFallback")}: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow={t("auth.signup.eyebrow")}>
      <Card>
        <CardHeader>
          <CardTitle>{t("auth.signup.title")}</CardTitle>
          <CardDescription>{t("auth.signup.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
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
              <Label htmlFor="signup-password">{t("auth.signup.passwordLabel")}</Label>
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
              {submitting && <Loader2 className="size-4 animate-spin" />}
              {submitting ? t("auth.signup.submitting") : t("auth.signup.submit")}
            </Button>
          </form>

          {error && (
            <Alert variant="destructive" className="mt-4" data-testid="signup-error">
              {error}
            </Alert>
          )}

          <p className="mt-5 text-center text-sm text-(--color-muted-foreground)">
            {t("auth.signup.alreadyHaveAccount")}{" "}
            <Link
              to="/login"
              className="font-medium text-(--color-foreground) underline-offset-4 hover:underline"
            >
              {t("auth.signup.loginLink")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
