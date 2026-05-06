import { authClient } from "../lib/auth-client";

export function Login() {
  const handleSignIn = async () => {
    await authClient.signIn.social({
      provider: "google",
      callbackURL: "/home",
    });
  };

  return (
    <main>
      <h1>Meeting Playbook</h1>
      <p>登入後可以開始準備會議</p>
      <button type="button" onClick={handleSignIn}>
        Sign in with Google
      </button>
    </main>
  );
}
