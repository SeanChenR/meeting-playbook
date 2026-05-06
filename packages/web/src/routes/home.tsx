import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { authClient } from "../lib/auth-client";

type ApiMeResponse = { user_id: string };

export function Home() {
  const { data: session, isPending } = authClient.useSession();
  const [backendUserId, setBackendUserId] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isPending) return;
    if (!session) {
      navigate("/login", { replace: true });
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/me");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = (await r.json()) as ApiMeResponse;
        if (!cancelled) setBackendUserId(data.user_id);
      } catch (e) {
        if (!cancelled) setBackendError(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session, isPending, navigate]);

  const handleLogout = async () => {
    await authClient.signOut();
    navigate("/login", { replace: true });
  };

  if (isPending)
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  if (!session) return null;

  const twoFactorEnabled = (session.user as { twoFactorEnabled?: boolean }).twoFactorEnabled;

  return (
    <main>
      <h1>Hello, {session.user.name ?? session.user.email}</h1>
      {backendUserId && (
        <p data-testid="backend-confirmation">
          Backend confirmed: <code>{backendUserId}</code>
        </p>
      )}
      {backendError && (
        <p data-testid="backend-error" role="alert">
          Backend round-trip failed: {backendError}
        </p>
      )}

      <section>
        <h2>帳號安全</h2>
        {twoFactorEnabled ? (
          <p data-testid="totp-status">✓ Two-factor authentication 已啟用</p>
        ) : (
          <p>
            <Link to="/totp/enroll" data-testid="enable-totp-link">
              Enable two-factor authentication
            </Link>
            <br />
            <small>需先設定 password（Google 登入帳號要先連結密碼）</small>
          </p>
        )}
      </section>

      <button type="button" onClick={handleLogout}>
        Logout
      </button>
    </main>
  );
}
