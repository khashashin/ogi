import { useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { Loader2 } from "lucide-react";

type AuthMode = "signin" | "signup" | "forgot";

export function AuthPage() {
  const { signIn, signUp, resetPassword } = useAuthStore();
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  const switchMode = (m: AuthMode) => {
    setMode(m);
    setError(null);
    setSignupSuccess(false);
    setResetSent(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);

    if (mode === "forgot") {
      const err = await resetPassword(email);
      setBusy(false);
      if (err) {
        setError(err);
      } else {
        setResetSent(true);
      }
      return;
    }

    const err =
      mode === "signin"
        ? await signIn(email, password)
        : await signUp(email, password);
    setBusy(false);
    if (err) {
      setError(err);
    } else if (mode === "signup") {
      setSignupSuccess(true);
    }
  };

  const title =
    mode === "signin"
      ? "Sign in to continue"
      : mode === "signup"
        ? "Create an account"
        : "Reset your password";

  return (
    <div className="flex items-center justify-center h-screen w-screen bg-bg">
      <div className="w-full max-w-sm p-6 bg-surface border border-border rounded-lg shadow-lg">
        <h1 className="text-lg font-semibold text-text mb-1">OpenGraph Intel</h1>
        <p className="text-xs text-text-muted mb-6">{title}</p>

        {signupSuccess ? (
          <div className="text-sm text-green-400">
            Check your email to confirm your account, then sign in.
          </div>
        ) : resetSent ? (
          <div className="text-sm text-green-400">
            Check your email for a password reset link.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            {mode !== "forgot" && (
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
              />
            )}
            {error && (
              <p className="text-xs text-danger">{error}</p>
            )}
            <button
              type="submit"
              disabled={busy}
              className="flex items-center justify-center gap-2 px-4 py-2 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              {mode === "signin"
                ? "Sign In"
                : mode === "signup"
                  ? "Sign Up"
                  : "Send Reset Link"}
            </button>
          </form>
        )}

        <div className="mt-4 flex flex-col items-center gap-1">
          {mode === "signin" && (
            <>
              <button
                onClick={() => switchMode("forgot")}
                className="text-xs text-text-muted hover:text-accent"
              >
                Forgot password?
              </button>
              <p className="text-xs text-text-muted">
                Don&apos;t have an account?{" "}
                <button
                  onClick={() => switchMode("signup")}
                  className="text-accent hover:underline"
                >
                  Sign up
                </button>
              </p>
            </>
          )}
          {mode === "signup" && (
            <p className="text-xs text-text-muted">
              Already have an account?{" "}
              <button
                onClick={() => switchMode("signin")}
                className="text-accent hover:underline"
              >
                Sign in
              </button>
            </p>
          )}
          {mode === "forgot" && (
            <p className="text-xs text-text-muted">
              Back to{" "}
              <button
                onClick={() => switchMode("signin")}
                className="text-accent hover:underline"
              >
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
