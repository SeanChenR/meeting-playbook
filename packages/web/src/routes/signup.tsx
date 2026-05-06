import { Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { AuthShell } from "../components/auth-shell";
import { Alert } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { authClient } from "../lib/auth-client";

export function Signup() {
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
      setError("密碼不一致");
      return;
    }
    if (password.length < 8) {
      setError("密碼至少 8 個字元");
      return;
    }

    setSubmitting(true);
    try {
      const result = await authClient.signUp.email({ email, password, name });
      const r = result as { error?: { message?: string } };
      if (r.error) {
        setError(r.error.message ?? "Signup failed");
        setSubmitting(false);
        return;
      }
      navigate("/home", { replace: true });
    } catch (e) {
      setError(`Signup failed: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="註冊">
      <Card>
        <CardHeader>
          <CardTitle>建立 Email 帳號</CardTitle>
          <CardDescription>使用 email 和密碼註冊，登入後可選擇啟用 2FA</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="signup-name">姓名</Label>
              <Input
                id="signup-name"
                type="text"
                autoComplete="name"
                placeholder="Sean Chen"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="signup-email">Email</Label>
              <Input
                id="signup-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="signup-password">Password</Label>
              <Input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                placeholder="至少 8 個字元"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="signup-confirm">Confirm password</Label>
              <Input
                id="signup-confirm"
                type="password"
                autoComplete="new-password"
                placeholder="再輸入一次"
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting && <Loader2 className="size-4 animate-spin" />}
              {submitting ? "註冊中" : "Sign up"}
            </Button>
          </form>

          {error && (
            <Alert variant="destructive" className="mt-4" data-testid="signup-error">
              {error}
            </Alert>
          )}

          <p className="mt-5 text-center text-sm text-(--color-muted-foreground)">
            已經有帳號？{" "}
            <Link
              to="/login"
              className="font-medium text-(--color-foreground) underline-offset-4 hover:underline"
            >
              回到登入
            </Link>
          </p>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
