import { create } from "zustand";

const STORAGE_KEY = "ogi-cookie-consent";

type ConsentValue = "granted" | "denied";

interface CookieConsentState {
  consent: ConsentValue | null;
  showBanner: boolean;
  acceptAll: () => void;
  rejectAll: () => void;
  resetConsent: () => void;
}

function readStoredConsent(): ConsentValue | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "granted" || value === "denied") return value;
    return null;
  } catch {
    return null;
  }
}

export const useCookieConsentStore = create<CookieConsentState>((set) => {
  const initial = readStoredConsent();

  return {
    consent: initial,
    showBanner: initial === null,

    acceptAll: () => {
      localStorage.setItem(STORAGE_KEY, "granted");
      set({ consent: "granted", showBanner: false });
    },

    rejectAll: () => {
      localStorage.setItem(STORAGE_KEY, "denied");
      set({ consent: "denied", showBanner: false });
    },

    resetConsent: () => {
      localStorage.removeItem(STORAGE_KEY);
      set({ consent: null, showBanner: true });
    },
  };
});
