import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { authClient } from "../../lib/auth-client";

export function TotpVerify() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

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
      <h1>Two-factor verification</h1>
      <p>輸入 Authenticator 顯示的 6 位數驗證碼</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="totp-verify-code">驗證碼</label>
        <input
          id="totp-verify-code"
          name="code"
          type="text"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
          autoFocus
        />
        <button type="submit">Verify</button>
      </form>
      {error && (
        <p role="alert" data-testid="totp-verify-error">
          {error}
        </p>
      )}
    </main>
  );
}
