import { useEffect, useRef, useState } from "react";
import { Clock, CreditCard, Server, X } from "lucide-react";
import {
  BILLING_COOLDOWN_EVENT,
  openProfileDialog,
  type BillingCooldownDetail,
} from "../lib/billingCooldownDialog";

export function BillingCooldownDialog() {
  const [detail, setDetail] = useState<BillingCooldownDetail | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (event: Event) => {
      const custom = event as CustomEvent<BillingCooldownDetail>;
      setDetail(custom.detail);
    };
    window.addEventListener(BILLING_COOLDOWN_EVENT, handler);
    return () => window.removeEventListener(BILLING_COOLDOWN_EVENT, handler);
  }, []);

  useEffect(() => {
    if (!detail) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDetail(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [detail]);

  useEffect(() => {
    if (!detail) return;
    const handler = (event: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(event.target as Node)) {
        setDetail(null);
      }
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [detail]);

  if (!detail) return null;

  const retryMinutes = detail.retryAfterSeconds
    ? Math.max(1, Math.ceil(detail.retryAfterSeconds / 60))
    : null;

  const handleOpenProfile = () => {
    setDetail(null);
    openProfileDialog();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div
        ref={dialogRef}
        className="w-full max-w-md rounded-lg border border-border bg-surface shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-warning" />
            <h2 className="text-sm font-semibold text-text">Free cloud cooldown</h2>
          </div>
          <button
            onClick={() => setDetail(null)}
            className="rounded p-1 text-text-muted hover:bg-surface-hover hover:text-text"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>

        <div className="space-y-4 px-4 py-4 text-sm leading-relaxed text-text-muted">
          {retryMinutes && (
            <div className="rounded border border-warning/35 bg-warning/10 px-3 py-2 text-xs text-warning">
              You can run another free transform in about {retryMinutes} minute
              {retryMinutes === 1 ? "" : "s"}.
            </div>
          )}

          <p>
            The hosted cloud version was built so users can test OGI quickly before
            deciding whether to self-host it. OGI is still fully open source and can
            be self-hosted completely free.
          </p>

          <div className="grid gap-2 text-xs">
            <div className="flex gap-2 rounded border border-border bg-bg px-3 py-2">
              <Server size={14} className="mt-0.5 shrink-0 text-accent" />
              <p>
                Free cloud accounts have a 30 minute cooldown between transform
                runs to keep the public infrastructure sustainable.
              </p>
            </div>
            <div className="flex gap-2 rounded border border-accent/35 bg-accent/10 px-3 py-2 text-text">
              <CreditCard size={14} className="mt-0.5 shrink-0 text-accent" />
              <p>
                A Supporter subscription helps cover infrastructure costs and
                removes the 30 minute transform cooldown.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              onClick={() => setDetail(null)}
              className="rounded border border-border px-3 py-1.5 text-xs text-text hover:bg-surface-hover"
            >
              Maybe later
            </button>
            <button
              onClick={handleOpenProfile}
              className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
            >
              Open subscription
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
