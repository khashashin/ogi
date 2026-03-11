import { useEffect } from "react";
import { Navigate, Outlet } from "react-router";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "../stores/authStore";

/**
 * Route guard: redirects to /login when auth is enabled and no user session exists.
 * In local dev mode (no Supabase), passes through immediately.
 * Calls initialize() on mount to restore the auth session.
 */
export function ProtectedRoute() {
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

  if (!authEnabled) {
    return <Outlet />;
  }

  if (isRecovery && user) {
    return <Navigate to="/reset-password" replace />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
