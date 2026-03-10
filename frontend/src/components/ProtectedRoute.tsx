import { Navigate } from "react-router";
import { useAuthStore } from "../stores/authStore";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * Route guard: redirects to /login when auth is enabled and no user session exists.
 * In local dev mode (no Supabase), passes through immediately.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { authEnabled, user, loading, isRecovery } = useAuthStore();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen w-screen bg-bg">
        <Loader2 size={24} className="animate-spin text-accent" />
      </div>
    );
  }

  // Recovery flow — redirect to reset password
  if (authEnabled && isRecovery && user) {
    return <Navigate to="/reset-password" replace />;
  }

  // Auth not configured (local dev) → allow through
  if (!authEnabled) {
    return <>{children}</>;
  }

  // No user → redirect to login
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
