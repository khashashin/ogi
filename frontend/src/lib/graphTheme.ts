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
