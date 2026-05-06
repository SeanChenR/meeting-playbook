import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
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
    <main>
      <h1>建立 Email 帳號</h1>
      <form onSubmit={handleSubmit}>
        <label htmlFor="signup-name">姓名</label>
        <input
          id="signup-name"
          type="text"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <label htmlFor="signup-confirm">Confirm password</label>
        <input
          id="signup-confirm"
          type="password"
          autoComplete="new-password"
          minLength={8}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
        <button type="submit" disabled={submitting}>
          {submitting ? "註冊中…" : "Sign up"}
        </button>
      </form>
      {error && (
        <p role="alert" data-testid="signup-error">
          {error}
        </p>
      )}
      <p>
        已經有帳號？<Link to="/login">回到登入</Link>
      </p>
    </main>
  );
}
