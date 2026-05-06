import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { QRCodeSVG } from "qrcode.react";
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
      if (r.data) {
        setEnrollData(r.data);
      }
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
      <main>
        <h1>Set up two-factor authentication</h1>
        <p>確認你的密碼以開始 TOTP 註冊。Google-only 登入帳號需先連結密碼。</p>
        <form onSubmit={handleEnableSubmit}>
          <label htmlFor="enroll-password">Password</label>
          <input
            id="enroll-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" disabled={submitting}>
            {submitting ? "驗證中…" : "Continue"}
          </button>
        </form>
        {error && (
          <p role="alert" data-testid="totp-error">
            {error}
          </p>
        )}
      </main>
    );
  }

  return (
    <main>
      <h1>Set up two-factor authentication</h1>
      <section>
        <p>用 Authenticator app 掃描 QR：</p>
        <QRCodeSVG value={enrollData.totpURI} size={192} />
      </section>
      <section>
        <h2>備援碼（請保存於安全的地方）</h2>
        <ul data-testid="backup-codes">
          {enrollData.backupCodes.map((c) => (
            <li key={c}>
              <code>{c}</code>
            </li>
          ))}
        </ul>
      </section>
      <form onSubmit={handleVerifySubmit}>
        <label htmlFor="totp-code">輸入 6 位數驗證碼</label>
        <input
          id="totp-code"
          name="code"
          type="text"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        <button type="submit">Verify</button>
      </form>
      {error && (
        <p role="alert" data-testid="totp-error">
          {error}
        </p>
      )}
    </main>
  );
}
