import type { RasterSourceSpecification } from "maplibre-gl";

import type { ResolvedTheme } from "../stores/themeStore";

export type Basemap = "dark" | "darkGray" | "darkMinimal" | "cartoLight" | "light" | "lightDetail" | "sat";

export interface BasemapOption {
  id: Basemap;
  label: string;
  source: RasterSourceSpecification;
}

function rasterSource(tiles: string[], attribution: string): RasterSourceSpecification {
  return { type: "raster", tiles, tileSize: 256, attribution };
}

/** CARTO serves an "API key required" watermark to keyless requests, so it needs a key. */
function cartoSource(style: string, apiKey: string): RasterSourceSpecification {
  const key = encodeURIComponent(apiKey);
  return rasterSource(
    ["a", "b"].map((host) => `https://${host}.basemaps.cartocdn.com/${style}/{z}/{x}/{y}.png?key=${key}`),
    "&copy; OpenStreetMap Contributors, &copy; CARTO",
  );
}

/** The selectable basemaps, default first. CARTO styles are offered only when a key is configured. */
export function getBasemapOptions(cartoApiKey: string | undefined): BasemapOption[] {
  const esriDarkGray: BasemapOption = {
    id: "darkGray",
    label: "Esri Dark Gray",
    source: rasterSource(
      ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
      "Tiles &copy; Esri",
    ),
  };
  const others: BasemapOption[] = [
    {
      id: "light",
      label: "OSM Standard",
      source: rasterSource(
        ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png"],
        "&copy; OpenStreetMap Contributors",
      ),
    },
    {
      id: "lightDetail",
      label: "OSM Humanitarian",
      source: rasterSource(
        ["https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"],
        "&copy; OpenStreetMap Contributors, Humanitarian OpenStreetMap Team",
      ),
    },
    {
      id: "sat",
      label: "Satellite (Esri)",
      source: rasterSource(
        ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        "Tiles &copy; Esri",
      ),
    },
  ];
  if (!cartoApiKey) return [esriDarkGray, ...others];
  return [
    { id: "dark", label: "CARTO Dark", source: cartoSource("dark_all", cartoApiKey) },
    esriDarkGray,
    { id: "darkMinimal", label: "CARTO Dark Minimal", source: cartoSource("dark_nolabels", cartoApiKey) },
    { id: "cartoLight", label: "CARTO Light", source: cartoSource("light_all", cartoApiKey) },
    ...others,
  ];
}

const PREFERRED_BASEMAPS: Record<ResolvedTheme, Basemap[]> = {
  dark: ["dark", "darkGray"],
  light: ["cartoLight", "light"],
};

/** The basemap the map opens on for a theme, out of the ones on offer. */
export function defaultBasemap(options: BasemapOption[], theme: ResolvedTheme): Basemap {
  const available = new Set(options.map((option) => option.id));
  return PREFERRED_BASEMAPS[theme].find((id) => available.has(id)) ?? options[0].id;
}

export function basemapLayerId(id: Basemap): string {
  return `basemap-${id}`;
}
