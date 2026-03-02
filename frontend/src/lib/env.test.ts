import { beforeEach, describe, expect, it, vi } from "vitest";

describe("getEnv", () => {
  beforeEach(() => {
    vi.resetModules();
    delete (window as Window & { __OGI_RUNTIME_CONFIG__?: Record<string, string> }).__OGI_RUNTIME_CONFIG__;
  });

  it("uses runtime config when present", async () => {
    (window as Window & { __OGI_RUNTIME_CONFIG__?: Record<string, string> }).__OGI_RUNTIME_CONFIG__ = {
      VITE_SUPABASE_URL: "https://runtime.supabase.co",
    };
    const { getEnv } = await import("./env");
    expect(getEnv("VITE_SUPABASE_URL")).toBe("https://runtime.supabase.co");
  });

  it("returns undefined when key is missing", async () => {
    const { getEnv } = await import("./env");
    expect(getEnv("VITE_SUPABASE_REDIRECT_URL")).toBeUndefined();
  });
});
