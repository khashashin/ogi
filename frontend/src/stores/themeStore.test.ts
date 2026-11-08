import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type ChangeListener = () => void;

interface FakeMediaQuery {
  setMatches: (matches: boolean) => void;
}

/** Install a controllable matchMedia; jsdom does not implement it. */
function installMatchMedia(initiallyLight: boolean): FakeMediaQuery {
  let matches = initiallyLight;
  const listeners: ChangeListener[] = [];
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      media: query,
      get matches() {
        return matches;
      },
      addEventListener: (_type: string, listener: ChangeListener) => listeners.push(listener),
      removeEventListener: () => {},
    }),
  });
  return {
    setMatches: (next) => {
      matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

async function loadStore() {
  vi.resetModules();
  const module = await import("./themeStore");
  return module.useThemeStore;
}

describe("themeStore", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    installMatchMedia(false);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("defaults to dark", async () => {
    const store = await loadStore();

    expect(store.getState().preference).toBe("dark");
    expect(store.getState().resolvedTheme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("restores the saved preference", async () => {
    localStorage.setItem("ogi-theme", "light");
    const store = await loadStore();

    expect(store.getState().resolvedTheme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("ignores an unknown saved value", async () => {
    localStorage.setItem("ogi-theme", "sepia");
    const store = await loadStore();

    expect(store.getState().preference).toBe("dark");
  });

  it("applies and saves a new preference", async () => {
    const store = await loadStore();

    store.getState().setPreference("light");

    expect(store.getState().resolvedTheme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("ogi-theme")).toBe("light");
  });

  it("follows the operating system when set to system", async () => {
    const media = installMatchMedia(true);
    localStorage.setItem("ogi-theme", "system");
    const store = await loadStore();
    expect(store.getState().resolvedTheme).toBe("light");

    media.setMatches(false);

    expect(store.getState().resolvedTheme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("stops following the operating system after an explicit choice", async () => {
    const media = installMatchMedia(false);
    localStorage.setItem("ogi-theme", "system");
    const store = await loadStore();

    store.getState().setPreference("dark");
    media.setMatches(true);

    expect(store.getState().resolvedTheme).toBe("dark");
  });
});
