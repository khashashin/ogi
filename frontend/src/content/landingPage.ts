import type { TransformInfo } from "../types/transform";

export const LANDING_PAGE_TITLE = "OpenGraph Intel | Open-Source OSINT Link Analysis Platform";
export const LANDING_PAGE_DESCRIPTION =
  "Investigate entities, map relationships, and run graph-native OSINT workflows with an open-source visual intelligence platform.";
export const LANDING_PAGE_KEYWORDS =
  "OSINT platform, link analysis, graph intelligence, open source intelligence, visual investigation, entity relationships, cybersecurity analysis";
export const DEFAULT_SITE_URL = "https://ogi.khas.app";

export const FEATURED_TRANSFORMS: TransformInfo[] = [
  {
    name: "username_search",
    display_name: "Username Search",
    description: "Searches public platforms and investigations sources for a username pivot.",
    input_types: ["Username"],
    output_types: ["SocialMedia", "URL", "Document"],
    category: "Identity",
    api_key_services: [],
    plugin_name: null,
    plugin_verification_tier: null,
    plugin_permissions: {},
    plugin_source: null,
    settings: [],
  },
  {
    name: "username_maigret",
    display_name: "Username to Maigret Accounts",
    description: "Uses Maigret-style enumeration to discover social and profile references for a username.",
    input_types: ["Username"],
    output_types: ["SocialMedia", "URL", "Document"],
    category: "Identity",
    api_key_services: [],
    plugin_name: "username-maigret",
    plugin_verification_tier: "community",
    plugin_permissions: { network: true, filesystem: false, subprocess: true },
    plugin_source: "local",
    settings: [],
  },
  {
    name: "domain_to_ip",
    display_name: "Domain to IP",
    description: "Resolves a domain to observed IP addresses for infrastructure pivoting.",
    input_types: ["Domain"],
    output_types: ["IPAddress"],
    category: "DNS",
    api_key_services: [],
    plugin_name: null,
    plugin_verification_tier: null,
    plugin_permissions: {},
    plugin_source: null,
    settings: [],
  },
  {
    name: "url_to_headers",
    display_name: "URL to HTTP Headers",
    description: "Collects notable HTTP headers from a target URL and turns them into graph evidence.",
    input_types: ["URL"],
    output_types: ["HTTPHeader"],
    category: "Web",
    api_key_services: [],
    plugin_name: null,
    plugin_verification_tier: null,
    plugin_permissions: {},
    plugin_source: null,
    settings: [],
  },
  {
    name: "email_to_domain",
    display_name: "Email to Domain",
    description: "Extracts the domain portion of an email address to start organization and infrastructure pivots.",
    input_types: ["EmailAddress"],
    output_types: ["Domain"],
    category: "Email",
    api_key_services: [],
    plugin_name: null,
    plugin_verification_tier: null,
    plugin_permissions: {},
    plugin_source: null,
    settings: [],
  },
];

export function createLandingStructuredData(siteUrl: string): Record<string, string> {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "OpenGraph Intel",
    applicationCategory: "SecurityApplication",
    operatingSystem: "Web",
    description:
      "Open-source visual intelligence platform for OSINT, link analysis, and graph-based investigation workflows.",
    url: siteUrl,
  };
}
