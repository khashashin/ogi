import { useEffect, useCallback } from "react";
import { useCookieConsentStore } from "../stores/cookieConsentStore";
import { GOOGLE_ANALYTICS_ID } from "../config/analytics";

const GTAG_SCRIPT_ID = "ogi-gtag-script";

const GA_COOKIES = ["_ga", "_gid", "_gat"];

function removeGACookies() {
  const hostname = window.location.hostname;
  const domains = [hostname, `.${hostname}`, ""];

  for (const name of GA_COOKIES) {
    for (const domain of domains) {
      const domainPart = domain ? `; domain=${domain}` : "";
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domainPart}`;
    }
  }
}

function injectGtagScript(measurementId: string) {
  if (document.getElementById(GTAG_SCRIPT_ID)) return;

  const script = document.createElement("script");
  script.id = GTAG_SCRIPT_ID;
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
  document.head.appendChild(script);

  const inlineScript = document.createElement("script");
  inlineScript.textContent = `
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', '${measurementId}');
  `;
  document.head.appendChild(inlineScript);
}

function removeGtagScript() {
  const script = document.getElementById(GTAG_SCRIPT_ID);
  if (script) script.remove();
}

interface WindowWithGtag extends Window {
  dataLayer: unknown[];
  gtag: (...args: unknown[]) => void;
}

export function useAnalytics() {
  const consent = useCookieConsentStore((s) => s.consent);

  useEffect(() => {
    if (!GOOGLE_ANALYTICS_ID) return;

    if (consent === "granted") {
      injectGtagScript(GOOGLE_ANALYTICS_ID);
    } else {
      removeGtagScript();
      removeGACookies();
    }
  }, [consent]);

  const trackPageView = useCallback(
    (path?: string) => {
      if (!GOOGLE_ANALYTICS_ID || consent !== "granted") return;

      const w = window as unknown as WindowWithGtag;
      if (typeof w.gtag === "function") {
        w.gtag("event", "page_view", {
          page_path: path ?? window.location.pathname,
        });
      }
    },
    [consent],
  );

  return { trackPageView };
}
