import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const DIST_DIR = resolve(process.cwd(), "dist");
const INDEX_HTML = resolve(DIST_DIR, "index.html");

if (!existsSync(INDEX_HTML)) {
  console.error("dist/index.html not found. Run vite build before sitemap generation.");
  process.exit(1);
}

const SITE_URL = (process.env.OGI_SITE_URL || process.env.SITE_URL || "https://ogi.khas.app").replace(/\/+$/, "");
const BUILD_DATE = new Date().toISOString().slice(0, 10);

/** Public, canonical routes only (exclude protected dynamic project pages). */
const ROUTES = [
  { path: "/", changefreq: "daily", priority: "1.0" },
  { path: "/discover", changefreq: "daily", priority: "0.9" },
  { path: "/terms", changefreq: "monthly", priority: "0.5" },
  { path: "/privacy", changefreq: "monthly", priority: "0.5" },
  { path: "/login", changefreq: "monthly", priority: "0.4" },
  { path: "/signup", changefreq: "monthly", priority: "0.4" },
  { path: "/forgot-password", changefreq: "monthly", priority: "0.3" },
  { path: "/reset-password", changefreq: "monthly", priority: "0.3" },
];

const urlsXml = ROUTES.map((route) => {
  const loc = `${SITE_URL}${route.path === "/" ? "" : route.path}`;
  return [
    "  <url>",
    `    <loc>${loc}</loc>`,
    `    <lastmod>${BUILD_DATE}</lastmod>`,
    `    <changefreq>${route.changefreq}</changefreq>`,
    `    <priority>${route.priority}</priority>`,
    "  </url>",
  ].join("\n");
}).join("\n");

const sitemapXml = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  urlsXml,
  "</urlset>",
  "",
].join("\n");

const robotsTxt = [
  "User-agent: *",
  "Allow: /",
  "",
  `Sitemap: ${SITE_URL}/sitemap.xml`,
  "",
].join("\n");

mkdirSync(DIST_DIR, { recursive: true });
writeFileSync(resolve(DIST_DIR, "sitemap.xml"), sitemapXml, "utf8");
writeFileSync(resolve(DIST_DIR, "robots.txt"), robotsTxt, "utf8");

console.log(`Generated sitemap.xml and robots.txt for ${SITE_URL}`);
