import { ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
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
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.twoFactor.verifyTotp({ code });
      const r = result as { data?: unknown; error?: { message?: string } | null };
      if (r.error) {
        setError(r.error.message ?? "驗證碼錯誤");
        setSubmitting(false);
        return;
      }
      // Force a session refresh so /home doesn't read a stale null cache and
      // bounce back to /login.
      await authClient.getSession();
      navigate("/home", { replace: true });
    } catch (e) {
      setError(`Code rejected: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="兩階段驗證">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-(--color-muted) p-2">
              <ShieldCheck className="size-4" />
            </span>
            <CardTitle className="text-lg">輸入驗證碼</CardTitle>
          </div>
          <CardDescription>輸入 Authenticator 顯示的 6 位數驗證碼</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="totp-verify-code">驗證碼</Label>
              <Input
                id="totp-verify-code"
                name="code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoFocus
                className="font-mono tracking-[0.4em] text-center text-base"
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full">
              {submitting ? "驗證中" : "Verify"}
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
