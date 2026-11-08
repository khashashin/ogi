import { useEffect } from "react";
import { useLocation } from "react-router";
import ReactGA from "react-ga4";
import { getEnv } from "../lib/env";
import { useCookieConsentStore } from "../stores/cookieConsentStore";

/** Cookies Google Analytics 4 sets: `_ga`, `_ga_<container>`, and the older `_gid` / `_gat`. */
function isGoogleAnalyticsCookie(name: string): boolean {
  return name === "_gid" || name === "_gat" || name.startsWith("_ga");
}

/**
 * The host and each parent domain, with and without a leading dot. GA writes its cookies on the
 * highest domain it may (e.g. `.khas.app` for `ogi.khas.app`), so expiring them needs that domain.
 */
function cookieDomains(hostname: string): string[] {
  const labels = hostname.split(".");
  const domains = [""];
  for (let i = 0; i < labels.length - 1; i += 1) {
    const domain = labels.slice(i).join(".");
    domains.push(domain, `.${domain}`);
  }
  return domains;
}

function removeGoogleAnalyticsCookies(): void {
  const names = document.cookie
    .split(";")
    .map((part) => part.split("=")[0]?.trim() ?? "")
    .filter(isGoogleAnalyticsCookie);
  for (const name of names) {
    for (const domain of cookieDomains(window.location.hostname)) {
      const domainPart = domain ? `; domain=${domain}` : "";
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domainPart}`;
    }
  }
}

/**
 * Google Analytics, active only after the visitor accepts analytics cookies in the consent banner.
 *
 * Nothing is loaded or sent while consent is undecided or rejected, and GA cookies are cleared then.
 * Withdrawing consent later (Profile → reset) switches GA's storage consent off for the rest of the
 * session. Page views are sent once per route, including the first one, so `config` is told not to
 * send its own.
 */
export function GoogleAnalytics() {
  const location = useLocation();
  const consent = useCookieConsentStore((state) => state.consent);
  const measurementId = getEnv("VITE_GA_MEASUREMENT_ID");
  const active = Boolean(measurementId) && consent === "granted";

  useEffect(() => {
    if (!measurementId) {
      console.warn("Google Analytics disabled (VITE_GA_MEASUREMENT_ID is missing)");
    }
  }, [measurementId]);

  useEffect(() => {
    if (active && measurementId) {
      if (ReactGA.isInitialized) {
        ReactGA.gtag("consent", "update", { analytics_storage: "granted" });
      } else {
        ReactGA.initialize(measurementId, { gtagOptions: { send_page_view: false } });
      }
      return;
    }
    if (ReactGA.isInitialized) {
      ReactGA.gtag("consent", "update", { analytics_storage: "denied" });
    }
    removeGoogleAnalyticsCookies();
  }, [active, measurementId]);

  useEffect(() => {
    if (!active) return;
    ReactGA.send({ hitType: "pageview", page: location.pathname + location.search });
  }, [active, location.pathname, location.search]);

  return null;
}
