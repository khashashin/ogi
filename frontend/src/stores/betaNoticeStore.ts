import { create } from "zustand";

const STORAGE_KEY = "ogi-beta-notice-dismissed";

interface BetaNoticeState {
  showNotice: boolean;
  dismiss: () => void;
}

function isDismissed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export const useBetaNoticeStore = create<BetaNoticeState>((set) => ({
  showNotice: !isDismissed(),

  dismiss: () => {
    localStorage.setItem(STORAGE_KEY, "true");
    set({ showNotice: false });
  },
}));
