import { act, useEffect } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useNavigate, type NavigateFunction } from "react-router";

import { useCookieConsentStore } from "../stores/cookieConsentStore";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

interface GaMock {
  isInitialized: boolean;
  initialize: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  gtag: ReturnType<typeof vi.fn>;
}

const ga = vi.hoisted<GaMock>(() => ({
  isInitialized: false,
  initialize: vi.fn(),
  send: vi.fn(),
  gtag: vi.fn(),
}));

const env = vi.hoisted<{ measurementId: string | undefined }>(() => ({ measurementId: "G-TEST123" }));

vi.mock("react-ga4", () => ({ default: ga }));
vi.mock("../lib/env", () => ({
  getEnv: (key: string) => (key === "VITE_GA_MEASUREMENT_ID" ? env.measurementId : undefined),
}));

import { GoogleAnalytics } from "./GoogleAnalytics";

const navigation: { current: NavigateFunction | null } = { current: null };

function NavigateProbe() {
  const navigate = useNavigate();
  useEffect(() => {
    navigation.current = navigate;
  }, [navigate]);
  return null;
}

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function render(initialPath = "/projects") {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root!.render(
      <MemoryRouter initialEntries={[initialPath]}>
        <GoogleAnalytics />
        <NavigateProbe />
      </MemoryRouter>,
    );
  });
}

function go(path: string) {
  act(() => {
    navigation.current?.(path);
  });
}

function setConsent(consent: "granted" | "denied" | null) {
  act(() => {
    useCookieConsentStore.setState({ consent, showBanner: consent === null });
  });
}

function pageViews(): string[] {
  return ga.send.mock.calls.map(([fields]) => (fields as { page: string }).page);
}

describe("GoogleAnalytics", () => {
  beforeEach(() => {
    ga.isInitialized = false;
    ga.initialize.mockReset().mockImplementation(() => {
      ga.isInitialized = true;
    });
    ga.send.mockReset();
    ga.gtag.mockReset();
    env.measurementId = "G-TEST123";
    useCookieConsentStore.setState({ consent: null, showBanner: true });
    document.cookie = "_ga=GA1.1.123.456; path=/";
    document.cookie = "_ga_TEST123=GS1.1.789; path=/";
    document.cookie = "ogi-other=keep; path=/";
  });

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = null;
    container = null;
    navigation.current = null;
    document.cookie = "ogi-other=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  it.each([null, "denied"] as const)("loads nothing and clears GA cookies while consent is %s", (consent) => {
    useCookieConsentStore.setState({ consent, showBanner: consent === null });
    render();
    go("/discover");

    expect(ga.initialize).not.toHaveBeenCalled();
    expect(ga.send).not.toHaveBeenCalled();
    expect(document.cookie).not.toContain("_ga");
    expect(document.cookie).toContain("ogi-other=keep");
  });

  it("initializes once after consent and sends one page view per route", () => {
    useCookieConsentStore.setState({ consent: "granted", showBanner: false });
    render("/projects");
    go("/discover");
    go("/discover?q=dns");

    expect(ga.initialize).toHaveBeenCalledTimes(1);
    expect(ga.initialize).toHaveBeenCalledWith("G-TEST123", { gtagOptions: { send_page_view: false } });
    expect(pageViews()).toEqual(["/projects", "/discover", "/discover?q=dns"]);
  });

  it("starts tracking the current page when consent is given during the visit", () => {
    render("/projects/abc");
    expect(ga.initialize).not.toHaveBeenCalled();

    setConsent("granted");

    expect(ga.initialize).toHaveBeenCalledTimes(1);
    expect(pageViews()).toEqual(["/projects/abc"]);
  });

  it("switches GA storage off and stops page views when consent is withdrawn", () => {
    useCookieConsentStore.setState({ consent: "granted", showBanner: false });
    render("/projects");
    document.cookie = "_ga=GA1.1.999; path=/";

    setConsent(null);
    go("/discover");

    expect(ga.gtag).toHaveBeenCalledWith("consent", "update", { analytics_storage: "denied" });
    expect(pageViews()).toEqual(["/projects"]);
    expect(document.cookie).not.toContain("_ga");

    setConsent("granted");
    expect(ga.initialize).toHaveBeenCalledTimes(1);
    expect(ga.gtag).toHaveBeenLastCalledWith("consent", "update", { analytics_storage: "granted" });
    expect(pageViews()).toEqual(["/projects", "/discover"]);
  });

  it("does nothing without a measurement ID, even with consent", () => {
    env.measurementId = undefined;
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    useCookieConsentStore.setState({ consent: "granted", showBanner: false });
    render();

    expect(ga.initialize).not.toHaveBeenCalled();
    expect(ga.send).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});
