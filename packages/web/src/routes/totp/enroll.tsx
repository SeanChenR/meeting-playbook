import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
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
        setError(r.error.message ?? "Enable failed");
        setSubmitting(false);
        return;
      }
      if (r.data) setEnrollData(r.data);
      setSubmitting(false);
    } catch (e) {
      setError(`Failed to start enrollment: ${e}`);
      setSubmitting(false);
    }
  };

  const handleVerifySubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    try {
      await authClient.twoFactor.verifyTotp({ code });
      navigate("/home", { replace: true });
    } catch (e) {
      setError(`Code rejected: ${e}`);
    }
  };

  if (!enrollData) {
    return (
      <AuthShell eyebrow="啟用 2FA">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2.5">
              <span className="rounded-md bg-(--color-muted) p-2">
                <KeyRound className="size-4" />
              </span>
              <CardTitle className="text-lg">Set up two-factor</CardTitle>
            </div>
            <CardDescription>
              請先確認密碼以開始 TOTP 註冊。Google-only 帳號需先連結密碼。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleEnableSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="enroll-password">Password</Label>
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
                {submitting ? "驗證中" : "Continue"}
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
    <AuthShell eyebrow="啟用 2FA · 步驟 2/2">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2.5">
            <span className="rounded-md bg-(--color-accent)/12 p-2 text-(--color-accent)">
              <ShieldCheck className="size-4" />
            </span>
            <CardTitle className="text-lg">掃描 QR 並驗證</CardTitle>
          </div>
          <CardDescription>用 Authenticator app 掃描，輸入 6 位數驗證碼完成設定</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex justify-center rounded-md border border-(--color-border) bg-(--color-card) p-4">
            <QRCodeSVG value={enrollData.totpURI} size={192} />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">備援碼</p>
            <p className="text-xs text-(--color-muted-foreground)">
              請保存於安全的地方，每組僅可使用一次
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
              <Label htmlFor="totp-code">輸入 6 位數驗證碼</Label>
              <Input
                id="totp-code"
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
                className="font-mono tracking-[0.4em] text-center text-base"
              />
            </div>
            <Button type="submit" className="w-full">
              Verify
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
