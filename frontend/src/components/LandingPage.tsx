import { useAuthStore } from "../stores/authStore";
import {
  DEFAULT_SITE_URL,
  LANDING_PAGE_DESCRIPTION,
  LANDING_PAGE_KEYWORDS,
  LANDING_PAGE_TITLE,
} from "../content/landingPage";
import { LandingPageStatic } from "./LandingPageStatic";
import { Seo } from "./Seo";

export function LandingPage() {
  const { user, authEnabled } = useAuthStore();
  const primaryHref = "/projects";
  const primaryLabel = authEnabled && user ? "Open Workspace" : "Start Investigating";
  const siteUrl = typeof window !== "undefined" ? window.location.origin : DEFAULT_SITE_URL;

  return (
    <>
      <Seo
        title={LANDING_PAGE_TITLE}
        description={LANDING_PAGE_DESCRIPTION}
        path="/"
        keywords={LANDING_PAGE_KEYWORDS}
      />
      <LandingPageStatic
        primaryHref={primaryHref}
        primaryLabel={primaryLabel}
        siteUrl={siteUrl}
      />
    </>
  );
}
