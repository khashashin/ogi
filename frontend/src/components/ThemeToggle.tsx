import { Monitor, Moon, Sun } from "lucide-react";
import { useThemeStore, type ThemePreference } from "../stores/themeStore";

const NEXT_PREFERENCE: Record<ThemePreference, ThemePreference> = {
  dark: "light",
  light: "system",
  system: "dark",
};

const PREFERENCE_LABEL: Record<ThemePreference, string> = {
  dark: "Dark theme",
  light: "Light theme",
  system: "System theme",
};

/** Cycles dark -> light -> system. */
export function ThemeToggle() {
  const preference = useThemeStore((state) => state.preference);
  const setPreference = useThemeStore((state) => state.setPreference);
  const next = NEXT_PREFERENCE[preference];
  const Icon = preference === "light" ? Sun : preference === "system" ? Monitor : Moon;
  const label = `${PREFERENCE_LABEL[preference]} (click for ${PREFERENCE_LABEL[next].toLowerCase()})`;

  return (
    <button
      type="button"
      onClick={() => setPreference(next)}
      className="p-1.5 rounded text-text-muted hover:text-text hover:bg-surface-hover"
      title={label}
      aria-label={label}
    >
      <Icon size={14} />
    </button>
  );
}
