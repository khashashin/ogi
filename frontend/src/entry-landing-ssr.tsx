import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import {
  LANDING_PAGE_DESCRIPTION,
  LANDING_PAGE_KEYWORDS,
  LANDING_PAGE_TITLE,
} from "./content/landingPage";
import { LandingPageStatic } from "./components/LandingPageStatic";

export interface LandingPageRenderResult {
  html: string;
  meta: {
    title: string;
    description: string;
    keywords: string;
    canonicalUrl: string;
    imageUrl: string;
  };
}

export function renderLandingPage(siteUrl: string): LandingPageRenderResult {
  const normalizedSiteUrl = siteUrl.replace(/\/+$/, "");
  const html = renderToStaticMarkup(
    <MemoryRouter initialEntries={["/"]}>
      <LandingPageStatic
        primaryHref="/projects"
        primaryLabel="Start Investigating"
        siteUrl={normalizedSiteUrl}
      />
    </MemoryRouter>,
  );

  return {
    html,
    meta: {
      title: LANDING_PAGE_TITLE,
      description: LANDING_PAGE_DESCRIPTION,
      keywords: LANDING_PAGE_KEYWORDS,
      canonicalUrl: `${normalizedSiteUrl}/`,
      imageUrl: `${normalizedSiteUrl}/ogi.svg`,
    },
  };
}
