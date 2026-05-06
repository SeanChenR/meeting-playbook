import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { authClient } from "../lib/auth-client";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleGoogleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/home",
    });
  };

  const handleEmailSignIn = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await authClient.signIn.email({ email, password });
      const r = result as {
        error?: { message?: string };
        data?: { twoFactorRedirect?: boolean };
      };
      if (r.error) {
        setError(r.error.message ?? "Sign in failed");
        setSubmitting(false);
        return;
      }
      if (r.data?.twoFactorRedirect) {
        navigate("/totp/verify", { replace: true });
        return;
      }
      navigate("/home", { replace: true });
    } catch (e) {
      setError(`Sign in failed: ${e}`);
      setSubmitting(false);
    }
  };

  return (
    <main>
      <h1>Meeting Playbook</h1>
      <p>登入後可以開始準備會議</p>

      <section>
        <h2>Google</h2>
        <button type="button" onClick={handleGoogleSignIn}>
          Sign in with Google
        </button>
      </section>

      <hr />

      <section>
        <h2>Email + Password</h2>
        <form onSubmit={handleEmailSignIn}>
          <label htmlFor="login-email">Email</label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" disabled={submitting}>
            {submitting ? "登入中…" : "Sign in"}
          </button>
        </form>
        {error && (
          <p role="alert" data-testid="login-error">
            {error}
          </p>
        )}
        <p>
          沒帳號？<Link to="/signup">建立帳號</Link>
        </p>
      </section>
    </main>
  );
}
