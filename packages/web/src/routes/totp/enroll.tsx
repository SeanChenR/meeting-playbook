import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { QRCodeSVG } from "qrcode.react";
import { authClient } from "../../lib/auth-client";

export function TotpEnroll() {
  const [totpUri, setTotpUri] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await authClient.twoFactor.enable({ password: "" });
        const data = (result as { data?: { totpURI?: string } }).data;
        if (!cancelled && data?.totpURI) {
          setTotpUri(data.totpURI);
        }
      } catch (e) {
        if (!cancelled) setError(`Failed to start enrollment: ${e}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      await authClient.twoFactor.verifyTotp({ code });
      navigate("/home", { replace: true });
    } catch (e) {
      setError(`Code rejected: ${e}`);
    }
  };

  return (
    <main>
      <h1>Set up two-factor authentication</h1>
      {totpUri ? (
        <div>
          <p>用 Authenticator app 掃描 QR：</p>
          <QRCodeSVG value={totpUri} size={192} />
        </div>
      ) : (
        <p>Loading QR…</p>
      )}
      <form onSubmit={handleSubmit}>
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
