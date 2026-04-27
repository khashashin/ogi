import { ApiError } from "../api/client";

export interface BillingCooldownDetail {
  message: string;
  retryAfterSeconds: number | null;
}

export const BILLING_COOLDOWN_EVENT = "ogi-billing-cooldown";
export const OPEN_PROFILE_EVENT = "ogi-open-profile";

export function openBillingCooldownDialog(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 429) {
    return false;
  }

  window.dispatchEvent(
    new CustomEvent<BillingCooldownDetail>(BILLING_COOLDOWN_EVENT, {
      detail: {
        message: error.message,
        retryAfterSeconds: error.retryAfterSeconds,
      },
    }),
  );
  return true;
}

export function openProfileDialog(): void {
  window.dispatchEvent(new Event(OPEN_PROFILE_EVENT));
}
