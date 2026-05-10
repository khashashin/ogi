import { useEffect } from "react";

interface SeoProps {
  title: string;
  description: string;
  path?: string;
  image?: string;
  keywords?: string;
}

function upsertMeta(selector: string, attributes: Record<string, string>): void {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    document.head.appendChild(element);
  }
  Object.entries(attributes).forEach(([key, value]) => {
    element?.setAttribute(key, value);
  });
}

function upsertLink(selector: string, rel: string, href: string): void {
  let element = document.head.querySelector<HTMLLinkElement>(selector);
  if (!element) {
    element = document.createElement("link");
    document.head.appendChild(element);
  }
  element.setAttribute("rel", rel);
  element.setAttribute("href", href);
}

export function Seo({ title, description, path = "/", image = "/ogi.svg", keywords }: SeoProps) {
  useEffect(() => {
    const origin = window.location.origin;
    const url = new URL(path, origin).toString();
    const imageUrl = new URL(image, origin).toString();

    document.title = title;
    upsertMeta('meta[name="description"]', { name: "description", content: description });
    upsertMeta('meta[name="title"]', { name: "title", content: title });
    if (keywords) {
      upsertMeta('meta[name="keywords"]', { name: "keywords", content: keywords });
    }
    upsertMeta('meta[property="og:title"]', { property: "og:title", content: title });
    upsertMeta('meta[property="og:description"]', { property: "og:description", content: description });
    upsertMeta('meta[property="og:url"]', { property: "og:url", content: url });
    upsertMeta('meta[property="og:image"]', { property: "og:image", content: imageUrl });
    upsertMeta('meta[property="twitter:title"]', { property: "twitter:title", content: title });
    upsertMeta('meta[property="twitter:description"]', { property: "twitter:description", content: description });
    upsertMeta('meta[property="twitter:url"]', { property: "twitter:url", content: url });
    upsertMeta('meta[property="twitter:image"]', { property: "twitter:image", content: imageUrl });
    upsertLink('link[rel="canonical"]', "canonical", url);
  }, [description, image, keywords, path, title]);

  return null;
}
