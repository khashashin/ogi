import { describe, expect, it } from "vitest";

import { BASE_EDGE_COLOR, getGraphPalette, themedEdgeColor } from "./graphTheme";

describe("graphTheme", () => {
  it("keeps the stored edge colour in the dark theme", () => {
    const dark = getGraphPalette("dark");

    expect(themedEdgeColor(BASE_EDGE_COLOR, dark)).toBe(BASE_EDGE_COLOR);
  });

  it("swaps the stored edge colour for the light theme's", () => {
    const light = getGraphPalette("light");

    expect(themedEdgeColor(BASE_EDGE_COLOR, light)).toBe(light.edge);
    expect(themedEdgeColor(undefined, light)).toBe(light.edge);
    expect(light.edge).not.toBe(BASE_EDGE_COLOR);
  });

  it("leaves edges with their own colour alone", () => {
    expect(themedEdgeColor("#ff0000", getGraphPalette("light"))).toBe("#ff0000");
  });

  it("uses dark label text on the light canvas", () => {
    expect(getGraphPalette("light").label).not.toBe(getGraphPalette("dark").label);
  });
});
