import type { ResolvedTheme } from "../stores/themeStore";

/**
 * Colour stored on graph edges. Sigma draws on a canvas, so CSS theme tokens do not
 * reach it; renderers swap this value for the active theme's edge colour instead.
 */
export const BASE_EDGE_COLOR = "#4b5563";

export interface LabelStyle {
  color: string;
  background: string;
}

export interface GraphPalette {
  theme: ResolvedTheme;
  label: string;
  edge: string;
  selectedEdge: string;
  hoveredEdge: string;
  selectedLabel: LabelStyle;
  pinnedLabel: LabelStyle;
  connectionLabel: LabelStyle;
  /** Ring drawn around person photos in exported images. */
  imageRing: string;
}

const DARK_PALETTE: GraphPalette = {
  theme: "dark",
  label: "#e1e4ed",
  edge: BASE_EDGE_COLOR,
  selectedEdge: "#60a5fa",
  hoveredEdge: "#93c5fd",
  selectedLabel: { color: "#111827", background: "#f3f4f6" },
  pinnedLabel: { color: "#dbeafe", background: "#1e3a8a" },
  connectionLabel: { color: "#fef3c7", background: "#92400e" },
  imageRing: "rgba(255,255,255,0.2)",
};

const LIGHT_PALETTE: GraphPalette = {
  theme: "light",
  label: "#1f2937",
  edge: "#8a90a2",
  selectedEdge: "#2563eb",
  hoveredEdge: "#60a5fa",
  selectedLabel: { color: "#f9fafb", background: "#1f2937" },
  pinnedLabel: { color: "#1e3a8a", background: "#dbeafe" },
  connectionLabel: { color: "#78350f", background: "#fde68a" },
  imageRing: "rgba(15,23,42,0.2)",
};

export function getGraphPalette(theme: ResolvedTheme): GraphPalette {
  return theme === "light" ? LIGHT_PALETTE : DARK_PALETTE;
}

/** The colour to draw an edge with: the theme's edge colour unless the edge has its own. */
export function themedEdgeColor(color: string | undefined, palette: GraphPalette): string {
  return !color || color === BASE_EDGE_COLOR ? palette.edge : color;
}

type Rgb = [number, number, number];

/** The light theme's background (--color-bg), which the graph canvas also uses. */
const LIGHT_BACKGROUND: Rgb = [0xf5, 0xf6, 0xfa];
/** WCAG 1.4.11 minimum contrast for icons and other graphics. */
const GRAPHIC_CONTRAST = 3;

function parseHexColor(color: string): Rgb | null {
  const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color.trim());
  if (!match) return null;
  const hex = match[1].length === 3 ? [...match[1]].map((digit) => digit + digit).join("") : match[1];
  return [0, 2, 4].map((start) => Number.parseInt(hex.slice(start, start + 2), 16)) as Rgb;
}

function relativeLuminance(rgb: Rgb): number {
  const [r, g, b] = rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(a: Rgb, b: Rgb): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

/** Contrast of a hex colour against the light background, or null for other colour formats. */
export function contrastOnLight(color: string): number | null {
  const rgb = parseHexColor(color);
  return rgb ? contrastRatio(rgb, LIGHT_BACKGROUND) : null;
}

function shade(rgb: Rgb, amount: number): Rgb {
  return rgb.map((value) => Math.round(value * (1 - amount))) as Rgb;
}

function readableOnLight(color: string): string {
  const rgb = parseHexColor(color);
  if (!rgb || contrastRatio(rgb, LIGHT_BACKGROUND) >= GRAPHIC_CONTRAST) return color;
  // Find the least shading towards black that reaches the target, so the hue is kept.
  let low = 0;
  let high = 1;
  for (let step = 0; step < 12; step++) {
    const middle = (low + high) / 2;
    if (contrastRatio(shade(rgb, middle), LIGHT_BACKGROUND) >= GRAPHIC_CONTRAST) high = middle;
    else low = middle;
  }
  return `#${shade(rgb, high).map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

const lightEntityColors = new Map<string, string>();

/**
 * The colour to draw an entity type's icon or node with. Type colours are picked for the dark
 * theme and many are pale 300/400 shades that all but vanish on a light background, so in the
 * light theme a colour under 3:1 is darkened just enough to reach it. Other colours, and every
 * colour in the dark theme, are returned unchanged.
 */
export function themedEntityColor(color: string, theme: ResolvedTheme): string {
  if (theme === "dark") return color;
  let themed = lightEntityColors.get(color);
  if (themed === undefined) {
    themed = readableOnLight(color);
    lightEntityColors.set(color, themed);
  }
  return themed;
}
