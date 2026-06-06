import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuthStore } from "../stores/authStore";
import { Loader2 } from "lucide-react";
import { Seo } from "./Seo";
import { getEnv } from "../lib/env";
import { Turnstile, type TurnstileHandle } from "./Turnstile";

type AuthMode = "signin" | "signup" | "forgot";
type AuthFeedback =
  | { mode: AuthMode; type: "error"; message: string }
  | { mode: AuthMode; type: "signup-success" }
  | { mode: AuthMode; type: "reset-sent" };

interface AuthPageProps {
  mode: AuthMode;
}

export function AuthPage({ mode }: AuthPageProps) {
  const { signIn, signUp, resetPassword } = useAuthStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<AuthFeedback | null>(null);
  const currentFeedback = feedback?.mode === mode ? feedback : null;

  const turnstileSiteKey = getEnv("VITE_TURNSTILE_SITE_KEY");
  const [captchaToken, setCaptchaToken] = useState("");
  const turnstileRef = useRef<TurnstileHandle>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);

    if (turnstileSiteKey && !captchaToken) {
      setFeedback({ mode, type: "error", message: "Please complete the verification." });
      return;
    }

    setBusy(true);

    let err: string | null;
    if (mode === "forgot") {
      err = await resetPassword(email, captchaToken || undefined);
    } else if (mode === "signin") {
      err = await signIn(email, password, captchaToken || undefined);
    } else {
      err = await signUp(email, password, captchaToken || undefined);
    }
    setBusy(false);

    // Turnstile tokens are single-use; refresh for the next attempt.
    if (turnstileSiteKey) {
      setCaptchaToken("");
      turnstileRef.current?.reset();
    }

    if (err) {
      setFeedback({ mode, type: "error", message: err });
    } else if (mode === "forgot") {
      setFeedback({ mode, type: "reset-sent" });
    } else if (mode === "signup") {
      setFeedback({ mode, type: "signup-success" });
    } else {
      navigate("/projects");
    }
  };

  const title =
    mode === "signin"
      ? "Sign in to continue"
      : mode === "signup"
        ? "Create an account"
        : "Reset your password";

  return (
    <>
      <Seo
        title={
          mode === "signin"
            ? "Sign In | OpenGraph Intel"
            : mode === "signup"
              ? "Create Account | OpenGraph Intel"
              : "Reset Password | OpenGraph Intel"
        }
        description={
          mode === "signin"
            ? "Sign in to OpenGraph Intel to access your investigations, projects, and graph-based OSINT workflows."
            : mode === "signup"
              ? "Create an OpenGraph Intel account to manage investigations and collaborate on graph-based OSINT projects."
              : "Reset your OpenGraph Intel password to regain access to your workspace."
        }
        path={mode === "signin" ? "/login" : mode === "signup" ? "/signup" : "/forgot-password"}
      />
      <div className="flex items-center justify-center h-screen w-screen bg-bg">
        <div className="w-full max-w-sm p-6 bg-surface border border-border rounded-lg shadow-lg">
          <h1 className="text-lg font-semibold text-text mb-1">OpenGraph Intel</h1>
          <p className="text-xs text-text-muted mb-6">{title}</p>

          {currentFeedback?.type === "signup-success" ? (
            <div className="text-sm text-green-400">
              Check your email to confirm your account, then sign in.
            </div>
          ) : currentFeedback?.type === "reset-sent" ? (
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
              {turnstileSiteKey && (
                <Turnstile
                  ref={turnstileRef}
                  siteKey={turnstileSiteKey}
                  onToken={setCaptchaToken}
                />
              )}
              {currentFeedback?.type === "error" && (
                <p className="text-xs text-danger">{currentFeedback.message}</p>
              )}
              {mode === "signup" && (
                <p className="text-[11px] text-text-muted text-center">
                  By signing up, you agree to our{" "}
                  <Link to="/terms" className="text-accent hover:underline">
                    Terms of Use
                  </Link>{" "}
                  and{" "}
                  <Link to="/privacy" className="text-accent hover:underline">
                    Privacy Policy
                  </Link>
                  .
                </p>
              )}
              <button
                type="submit"
                disabled={busy || (!!turnstileSiteKey && !captchaToken)}
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
                <Link
                  to="/forgot-password"
                  className="text-xs text-text-muted hover:text-accent"
                >
                  Forgot password?
                </Link>
                <p className="text-xs text-text-muted">
                  Don&apos;t have an account?{" "}
                  <Link
                    to="/signup"
                    className="text-accent hover:underline"
                  >
                    Sign up
                  </Link>
                </p>
              </>
            )}
            {mode === "signup" && (
              <p className="text-xs text-text-muted">
                Already have an account?{" "}
                <Link
                  to="/login"
                  className="text-accent hover:underline"
                >
                  Sign in
                </Link>
              </p>
            )}
            {mode === "forgot" && (
              <p className="text-xs text-text-muted">
                Back to{" "}
                <Link
                  to="/login"
                  className="text-accent hover:underline"
                >
                  Sign in
                </Link>
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
