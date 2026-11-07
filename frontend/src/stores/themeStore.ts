import { create } from "zustand";

const STORAGE_KEY = "ogi-theme";
const LIGHT_QUERY = "(prefers-color-scheme: light)";

export type ThemePreference = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

interface ThemeState {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
}

function readStoredPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "dark" || value === "light" || value === "system") return value;
  } catch {
    // Storage can be unavailable (private mode, blocked site data); fall back to the default.
  }
  return "dark";
}

function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia(LIGHT_QUERY).matches ? "light" : "dark";
}

function resolve(preference: ThemePreference): ResolvedTheme {
  return preference === "system" ? systemTheme() : preference;
}

/** Point the CSS colour tokens at the theme; index.html applies the stored theme before first paint. */
function applyTheme(theme: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
  const background = getComputedStyle(document.documentElement).getPropertyValue("--color-bg").trim();
  if (background) {
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", background);
  }
}

export const useThemeStore = create<ThemeState>((set, get) => {
  const preference = readStoredPreference();
  const resolvedTheme = resolve(preference);
  applyTheme(resolvedTheme);

  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    window.matchMedia(LIGHT_QUERY).addEventListener("change", () => {
      if (get().preference !== "system") return;
      const next = systemTheme();
      applyTheme(next);
      set({ resolvedTheme: next });
    });
  }

  return {
    preference,
    resolvedTheme,

    setPreference: (next) => {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Not persisted, but still applied for this session.
      }
      const resolved = resolve(next);
      applyTheme(resolved);
      set({ preference: next, resolvedTheme: resolved });
    },
  };
});
