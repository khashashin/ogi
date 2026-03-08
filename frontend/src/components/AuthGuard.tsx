import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { AuthPage } from "./AuthPage";
import { ResetPasswordPage } from "./ResetPasswordPage";

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * If Supabase is configured, shows the auth page when no session exists.
 * If Supabase is NOT configured (local dev), renders children immediately.
 * If the user arrived via a recovery link, shows the reset password page.
 */
export function AuthGuard({ children }: AuthGuardProps) {
  const { authEnabled, user, loading, isRecovery, initialize } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen w-screen bg-bg">
        <Loader2 size={24} className="animate-spin text-accent" />
      </div>
    );
  }

  // Auth not configured → allow through
  if (!authEnabled) {
    return <>{children}</>;
  }

  // Recovery flow — user has a valid session from the recovery link
  if (isRecovery && user) {
    return <ResetPasswordPage />;
  }

  // Auth configured but no user → show auth page
  if (!user) {
    return <AuthPage />;
  }

  return <>{children}</>;
}
