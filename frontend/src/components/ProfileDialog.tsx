import { useState, useEffect, useRef } from "react";
import { Link } from "react-router";
import { X, LogOut, Loader2, Key, Cookie, FileText, Shield, CreditCard } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { useCookieConsentStore } from "../stores/cookieConsentStore";
import { api } from "../api/client";
import type { BillingStatus, CapabilitiesResponse } from "../api/client";

interface ProfileDialogProps {
  open: boolean;
  onClose: () => void;
  onOpenApiKeys: () => void;
  capabilities?: CapabilitiesResponse | null;
}

export function ProfileDialog({ open, onClose, onOpenApiKeys, capabilities }: ProfileDialogProps) {
  if (!open) return null;

  return (
    <ProfileDialogContent
      onClose={onClose}
      onOpenApiKeys={onOpenApiKeys}
      capabilities={capabilities}
    />
  );
}

function ProfileDialogContent({ onClose, onOpenApiKeys, capabilities }: Omit<ProfileDialogProps, "open">) {
  const { user, signOut, updateProfile, authEnabled } = useAuthStore();
  const resetConsent = useCookieConsentStore((s) => s.resetConsent);
  const currentDisplayName = (user?.user_metadata?.display_name as string) ?? "";
  const [displayName, setDisplayName] = useState(currentDisplayName);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingAction, setBillingAction] = useState<"checkout" | "portal" | "cancel" | null>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const userEmail = user?.email ?? "anonymous";

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [onClose]);

  useEffect(() => {
    if (capabilities?.cloud_billing_enabled === false) {
      setBillingStatus(null);
      setBillingLoading(false);
      setBillingError(null);
      return;
    }
    let cancelled = false;
    setBillingLoading(true);
    setBillingError(null);
    api.billing
      .status()
      .then((status) => {
        if (!cancelled) setBillingStatus(status.billing_enabled ? status : null);
      })
      .catch((err) => {
        if (!cancelled) setBillingError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setBillingLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [capabilities?.cloud_billing_enabled]);

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

  const handleBillingAction = async () => {
    if (!billingStatus) return;
    setBillingError(null);
    const action = billingStatus.subscribed ? "portal" : "checkout";
    setBillingAction(action);
    try {
      const session = billingStatus.subscribed
        ? await api.billing.customerPortal()
        : await api.billing.checkoutSession();
      window.location.href = session.url;
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : String(err));
    } finally {
      setBillingAction(null);
    }
  };

  const handleCancelSubscription = async () => {
    if (!billingStatus?.subscribed || billingStatus.cancel_at_period_end) return;
    const confirmed = window.confirm(
      "Cancel your Supporter subscription? You will keep Supporter access until the end of the current billing period.",
    );
    if (!confirmed) return;
    setBillingError(null);
    setBillingAction("cancel");
    try {
      const status = await api.billing.cancelSubscription();
      setBillingStatus(status.billing_enabled ? status : null);
    } catch (err) {
      setBillingError(err instanceof Error ? err.message : String(err));
    } finally {
      setBillingAction(null);
    }
  };

  const formatMoney = (status: BillingStatus) =>
    new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: status.currency || "usd",
      maximumFractionDigits: 2,
    }).format(status.amount_cents / 100);

  const formatDate = (value: string | null) =>
    value
      ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value))
      : null;

  const cooldownMinutes = billingStatus
    ? Math.max(1, Math.ceil(billingStatus.free_transform_cooldown_seconds / 60))
    : 30;
  const retryMinutes = billingStatus?.retry_after_seconds
    ? Math.max(1, Math.ceil(billingStatus.retry_after_seconds / 60))
    : 0;

  const initials = currentDisplayName
    ? currentDisplayName.slice(0, 2).toUpperCase()
    : userEmail.slice(0, 2).toUpperCase();
  const primaryBillingAction = billingStatus?.subscribed ? "portal" : "checkout";
  const currentPeriodEnd = formatDate(billingStatus?.current_period_end ?? null);

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
            {(billingLoading || billingStatus || billingError) && (
              <div className="px-2 py-2 mb-1 rounded bg-bg text-xs text-text-muted leading-relaxed">
                <div className="flex items-start gap-2">
                  <CreditCard size={13} className="mt-0.5 text-text-muted shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-text">
                        {billingStatus?.subscribed ? "Supporter" : "Cloud Free"}
                      </p>
                      {billingStatus && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={handleBillingAction}
                            disabled={
                              billingAction !== null ||
                              (!billingStatus.subscribed && !billingStatus.checkout_enabled)
                            }
                            className="px-2 py-1 text-[11px] bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50 flex items-center gap-1"
                          >
                            {billingAction === primaryBillingAction && (
                              <Loader2 size={11} className="animate-spin" />
                            )}
                            {billingStatus.subscribed ? "Manage" : "Upgrade"}
                          </button>
                          {billingStatus.subscribed && !billingStatus.cancel_at_period_end && (
                            <button
                              onClick={handleCancelSubscription}
                              disabled={billingAction !== null}
                              className="px-2 py-1 text-[11px] bg-surface border border-border text-text rounded hover:bg-surface-hover disabled:opacity-50 flex items-center gap-1"
                            >
                              {billingAction === "cancel" && (
                                <Loader2 size={11} className="animate-spin" />
                              )}
                              Cancel
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                    {billingLoading ? (
                      <p>Loading billing status...</p>
                    ) : billingStatus?.subscribed && billingStatus.cancel_at_period_end ? (
                      <p>
                        Your {billingStatus.plan_name} plan remains active
                        {currentPeriodEnd ? ` until ${currentPeriodEnd}` : ""}. Renewal is cancelled.
                      </p>
                    ) : billingStatus?.subscribed ? (
                      <p>
                        Your {billingStatus.plan_name} plan is active.
                      </p>
                    ) : billingStatus ? (
                      <p>
                        Free cloud accounts can run one transform every {cooldownMinutes} minutes.
                        Upgrade for {formatMoney(billingStatus)}/month.
                      </p>
                    ) : null}
                    {retryMinutes > 0 && (
                      <p className="mt-1 text-warning">Next free run in about {retryMinutes} minute{retryMinutes === 1 ? "" : "s"}.</p>
                    )}
                    {billingError && <p className="mt-1 text-danger">{billingError}</p>}
                  </div>
                </div>
              </div>
            )}
            {capabilities?.telemetry_enabled && (
              <div className="px-2 py-2 mb-1 rounded bg-bg text-xs text-text-muted leading-relaxed">
                Usage telemetry is currently on at the{" "}
                <span className="text-text">{capabilities.telemetry_level}</span> level. You can adjust
                it with the `OGI_TELEMETRY_ENABLED` and `OGI_TELEMETRY_LEVEL` environment settings.{" "}
                <a href={capabilities.telemetry_docs_url} className="text-accent hover:underline">
                  Learn more
                </a>
                .
              </div>
            )}
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
