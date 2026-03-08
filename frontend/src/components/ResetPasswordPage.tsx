import { useState } from "react";
import { useAuthStore } from "../stores/authStore";
import { Loader2, CheckCircle } from "lucide-react";

export function ResetPasswordPage() {
  const { updatePassword, clearRecovery } = useAuthStore();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    setBusy(true);
    const err = await updatePassword(password);
    setBusy(false);

    if (err) {
      setError(err);
    } else {
      setSuccess(true);
    }
  };

  return (
    <div className="flex items-center justify-center h-screen w-screen bg-bg">
      <div className="w-full max-w-sm p-6 bg-surface border border-border rounded-lg shadow-lg">
        <h1 className="text-lg font-semibold text-text mb-1">OpenGraph Intel</h1>
        <p className="text-xs text-text-muted mb-6">Set a new password</p>

        {success ? (
          <div className="flex flex-col items-center gap-3">
            <CheckCircle size={32} className="text-green-400" />
            <p className="text-sm text-green-400 text-center">
              Password updated successfully!
            </p>
            <button
              onClick={clearRecovery}
              className="px-4 py-2 text-sm bg-accent text-white rounded hover:bg-accent-hover"
            >
              Continue to OpenGraph Intel
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="password"
              placeholder="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            <input
              type="password"
              placeholder="Confirm password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              minLength={6}
              className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            {error && <p className="text-xs text-danger">{error}</p>}
            <button
              type="submit"
              disabled={busy}
              className="flex items-center justify-center gap-2 px-4 py-2 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              Update Password
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
