import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

const DIST_DIR = resolve(process.cwd(), "dist");
const DIST_SSR_DIR = resolve(process.cwd(), "dist-ssr");
const INDEX_HTML = resolve(DIST_DIR, "index.html");

if (!existsSync(INDEX_HTML)) {
  console.error("dist/index.html not found. Run vite build before prerendering.");
  process.exit(1);
}

if (!existsSync(DIST_SSR_DIR)) {
  console.error("dist-ssr not found. Run the SSR build before prerendering.");
  process.exit(1);
}

const ssrEntryName = readdirSync(DIST_SSR_DIR).find((entry) => entry.endsWith(".js") || entry.endsWith(".mjs"));
if (!ssrEntryName) {
  console.error("No SSR entry file found in dist-ssr.");
  process.exit(1);
}

const { renderLandingPage } = await import(pathToFileURL(resolve(DIST_SSR_DIR, ssrEntryName)).href);
const siteUrl = (process.env.OGI_SITE_URL || process.env.SITE_URL || "https://ogi.khas.app").replace(/\/+$/, "");

const { html, meta } = renderLandingPage(siteUrl);
let indexHtml = readFileSync(INDEX_HTML, "utf8");

function replaceTag(source, pattern, replacement) {
  if (pattern.test(source)) {
    return source.replace(pattern, replacement);
  }
  return source;
}

indexHtml = indexHtml.replace(
  /<div id="root"><\/div>/,
  `<div id="root" data-prerendered="true">${html}</div>`,
);

indexHtml = replaceTag(indexHtml, /<title>[\s\S]*?<\/title>/i, `<title>${meta.title}</title>`);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+name="title"\s+content="[^"]*"\s*\/?>/i,
  `<meta name="title" content="${meta.title}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+name="description"\s+content="[^"]*"\s*\/?>/i,
  `<meta name="description" content="${meta.description}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+name="keywords"\s+content="[^"]*"\s*\/?>/i,
  `<meta name="keywords" content="${meta.keywords}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="og:url"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="og:url" content="${meta.canonicalUrl}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="og:title"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="og:title" content="${meta.title}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="og:description"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="og:description" content="${meta.description}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="og:image"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="og:image" content="${meta.imageUrl}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="twitter:url"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="twitter:url" content="${meta.canonicalUrl}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="twitter:title"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="twitter:title" content="${meta.title}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="twitter:description"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="twitter:description" content="${meta.description}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<meta\s+property="twitter:image"\s+content="[^"]*"\s*\/?>/i,
  `<meta property="twitter:image" content="${meta.imageUrl}" />`,
);
indexHtml = replaceTag(
  indexHtml,
  /<link\s+rel="canonical"\s+href="[^"]*"\s*\/?>/i,
  `<link rel="canonical" href="${meta.canonicalUrl}" />`,
);

writeFileSync(INDEX_HTML, indexHtml, "utf8");
console.log(`Prerendered landing page for ${siteUrl}`);
