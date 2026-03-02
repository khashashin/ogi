import { create } from "zustand";
import { supabase } from "../lib/supabase";
import type { Session, User } from "@supabase/supabase-js";
import { getEnv } from "../lib/env";

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  /** true when Supabase credentials are configured */
  authEnabled: boolean;
  /** true when the user arrived via a recovery link */
  isRecovery: boolean;

  initialize: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<string | null>;
  updatePassword: (newPassword: string) => Promise<string | null>;
  updateProfile: (displayName: string) => Promise<string | null>;
  clearRecovery: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  session: null,
  loading: true,
  authEnabled: supabase !== null,
  isRecovery: false,

  initialize: async () => {
    if (!supabase) {
      set({ loading: false });
      return;
    }

    // Restore session from storage
    const {
      data: { session },
    } = await supabase.auth.getSession();
    set({ session, user: session?.user ?? null, loading: false });

    // Listen for auth state changes
    supabase.auth.onAuthStateChange((event, session) => {
      set({ session, user: session?.user ?? null });

      // Supabase fires PASSWORD_RECOVERY when a recovery token is consumed
      if (event === "PASSWORD_RECOVERY") {
        set({ isRecovery: true });
      }
    });
  },

  signIn: async (email, password) => {
    if (!supabase) return "Auth not configured";
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return error ? error.message : null;
  },

  signUp: async (email, password) => {
    if (!supabase) return "Auth not configured";
    const redirectUrl = getEnv("VITE_SUPABASE_REDIRECT_URL") || window.location.origin;
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectUrl,
      },
    });
    return error ? error.message : null;
  },

  signOut: async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    set({ user: null, session: null, isRecovery: false });
  },

  resetPassword: async (email) => {
    if (!supabase) return "Auth not configured";
    const redirectUrl = getEnv("VITE_SUPABASE_REDIRECT_URL") || window.location.origin;
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: redirectUrl,
    });
    return error ? error.message : null;
  },

  updatePassword: async (newPassword) => {
    if (!supabase) return "Auth not configured";
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    if (error) return error.message;
    set({ isRecovery: false });
    return null;
  },

  updateProfile: async (displayName) => {
    if (!supabase) return "Auth not configured";
    const { data, error } = await supabase.auth.updateUser({
      data: { display_name: displayName },
    });
    if (error) return error.message;
    if (data.user) set({ user: data.user });
    return null;
  },

  clearRecovery: () => set({ isRecovery: false }),
}));
