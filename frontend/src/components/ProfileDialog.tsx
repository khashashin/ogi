import { useState, useEffect, useRef } from "react";
import { Link } from "react-router";
import { X, LogOut, Loader2, Key, Puzzle, Cookie, FileText, Shield } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { useCookieConsentStore } from "../stores/cookieConsentStore";

interface ProfileDialogProps {
  open: boolean;
  onClose: () => void;
  onOpenApiKeys: () => void;
  onOpenPlugins: () => void;
}

export function ProfileDialog({ open, onClose, onOpenApiKeys, onOpenPlugins }: ProfileDialogProps) {
  const { user, signOut, updateProfile, authEnabled } = useAuthStore();
  const resetConsent = useCookieConsentStore((s) => s.resetConsent);
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const userEmail = user?.email ?? "anonymous";
  const currentDisplayName = (user?.user_metadata?.display_name as string) ?? "";

  useEffect(() => {
    if (open) {
      setDisplayName(currentDisplayName);
      setError(null);
      setSaved(false);
    }
  }, [open, currentDisplayName]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  const handleSaveProfile = async () => {
    setError(null);
    setSaving(true);
    setSaved(false);
    const err = await updateProfile(displayName.trim());
    setSaving(false);
    if (err) {
      setError(err);
    } else {
      setSaved(true);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    onClose();
  };

  if (!open) return null;

  const initials = currentDisplayName
    ? currentDisplayName.slice(0, 2).toUpperCase()
    : userEmail.slice(0, 2).toUpperCase();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div
        ref={dialogRef}
        className="w-full max-w-sm bg-surface border border-border rounded-lg shadow-lg"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Profile</h2>
          <button
            onClick={onClose}
            className="p-1 text-text-muted hover:text-text rounded"
          >
            <X size={14} />
          </button>
        </div>

        <div className="p-4 flex flex-col gap-4">
          {/* Avatar + Email */}
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-accent flex items-center justify-center text-white text-sm font-semibold shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              {currentDisplayName && (
                <p className="text-sm font-medium text-text truncate">
                  {currentDisplayName}
                </p>
              )}
              <p className="text-xs text-text-muted truncate">{userEmail}</p>
            </div>
          </div>

          {/* Display Name */}
          {authEnabled && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-text-muted">Display name</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => {
                    setDisplayName(e.target.value);
                    setSaved(false);
                  }}
                  placeholder="Enter a display name"
                  className="flex-1 px-3 py-1.5 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
                />
                <button
                  onClick={handleSaveProfile}
                  disabled={saving || displayName.trim() === currentDisplayName}
                  className="px-3 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50 flex items-center gap-1.5"
                >
                  {saving && <Loader2 size={12} className="animate-spin" />}
                  Save
                </button>
              </div>
              {error && <p className="text-xs text-danger">{error}</p>}
              {saved && (
                <p className="text-xs text-green-400">Profile updated.</p>
              )}
            </div>
          )}

          {/* Quick Links */}
          <div className="flex flex-col gap-1 border-t border-border pt-3">
            <button
              onClick={() => {
                onClose();
                onOpenApiKeys();
              }}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-text hover:bg-surface-hover rounded w-full text-left"
            >
              <Key size={13} className="text-text-muted" />
              API Keys
            </button>
            <button
              onClick={() => {
                onClose();
                onOpenPlugins();
              }}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-text hover:bg-surface-hover rounded w-full text-left"
            >
              <Puzzle size={13} className="text-text-muted" />
              Plugins
            </button>
            <button
              onClick={() => {
                onClose();
                resetConsent();
              }}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-text hover:bg-surface-hover rounded w-full text-left"
            >
              <Cookie size={13} className="text-text-muted" />
              Cookie Preferences
            </button>
          </div>

          {/* Legal Links */}
          <div className="flex flex-col gap-1 border-t border-border pt-3">
            <Link
              to="/privacy"
              onClick={onClose}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-text hover:bg-surface-hover rounded w-full"
            >
              <Shield size={13} className="text-text-muted" />
              Privacy Policy
            </Link>
            <Link
              to="/terms"
              onClick={onClose}
              className="flex items-center gap-2 px-2 py-1.5 text-xs text-text hover:bg-surface-hover rounded w-full"
            >
              <FileText size={13} className="text-text-muted" />
              Terms of Use
            </Link>
          </div>

          {/* Sign Out */}
          {authEnabled && (
            <div className="border-t border-border pt-3">
              <button
                onClick={handleSignOut}
                className="flex items-center gap-2 px-2 py-1.5 text-xs text-danger hover:bg-surface-hover rounded w-full text-left"
              >
                <LogOut size={13} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
