import { describe, expect, it } from "vitest";

import { defaultBasemap, getBasemapOptions } from "./basemaps";

function allTileUrls(cartoApiKey: string | undefined): string[] {
  return getBasemapOptions(cartoApiKey).flatMap((option) => option.source.tiles ?? []);
}

describe("getBasemapOptions", () => {
  it("leaves CARTO out without a key, since keyless CARTO tiles are watermarked", () => {
    const options = getBasemapOptions(undefined);

    expect(options[0].id).toBe("darkGray");
    expect(options.map((option) => option.id)).not.toContain("dark");
    expect(allTileUrls(undefined).some((url) => url.includes("cartocdn.com"))).toBe(false);
  });

  it("offers CARTO first and sends the key on every CARTO tile when a key is set", () => {
    const options = getBasemapOptions("abc 123&x");
    const cartoUrls = allTileUrls("abc 123&x").filter((url) => url.includes("cartocdn.com"));

    expect(options[0].id).toBe("dark");
    expect(options.map((option) => option.id)).toContain("darkMinimal");
    expect(cartoUrls.length).toBeGreaterThan(0);
    cartoUrls.forEach((url) => expect(url.endsWith("?key=abc%20123%26x")).toBe(true));
  });

  it("opens on a basemap that matches the theme", () => {
    const keyless = getBasemapOptions(undefined);
    const withKey = getBasemapOptions("k");

    expect(defaultBasemap(keyless, "dark")).toBe("darkGray");
    expect(defaultBasemap(keyless, "light")).toBe("light");
    expect(defaultBasemap(withKey, "dark")).toBe("dark");
    expect(defaultBasemap(withKey, "light")).toBe("cartoLight");
  });

  it("never sends the CARTO key to other providers", () => {
    const otherUrls = allTileUrls("secret").filter((url) => !url.includes("cartocdn.com"));

    expect(otherUrls.length).toBeGreaterThan(0);
    otherUrls.forEach((url) => expect(url).not.toContain("secret"));
  });
});
