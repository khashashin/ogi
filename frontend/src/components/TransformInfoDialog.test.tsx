import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { TransformInfoDialog } from "./TransformInfoDialog";
import type { TransformDocumentation, TransformInfo } from "../types/transform";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api/client", () => ({
  api: {
    transforms: {
      getDocumentation: vi.fn(),
    },
  },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const transform: TransformInfo = {
  name: "domain_to_ip",
  display_name: "Domain to IP Address",
  description: "Resolves A and AAAA records for a domain",
  input_types: ["Domain"],
  output_types: ["IPAddress"],
  category: "DNS",
  api_key_services: [],
  plugin_name: null,
  plugin_verification_tier: null,
  plugin_permissions: {},
  plugin_source: null,
  settings: [],
};

function makeDoc(overrides: Partial<TransformDocumentation> = {}): TransformDocumentation {
  return {
    name: "domain_to_ip",
    display_name: "Domain to IP Address",
    description: "Resolves A and AAAA records for a domain",
    long_description: "Performs a DNS lookup of A and AAAA records.",
    when_to_use: "Use this first when pivoting from a domain to infrastructure.",
    limitations: "Returns only current DNS answers, not historical ones.",
    example_use_cases: ["Map a domain to its hosting infrastructure"],
    input_types: ["Domain"],
    output_types: ["IPAddress"],
    category: "DNS",
    api_key_services: [],
    setting_names: [],
    source: "builtin",
    plugin_name: null,
    plugin_version: "",
    plugin_author: "",
    plugin_verification_tier: null,
    plugin_homepage: "",
    plugin_repository: "",
    readme: "",
    ...overrides,
  };
}

function renderDialog(open = true) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(<TransformInfoDialog open={open} transform={transform} onClose={() => {}} />);
  });

  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe("TransformInfoDialog", () => {
  beforeEach(() => {
    vi.mocked(api.transforms.getDocumentation).mockReset().mockResolvedValue(makeDoc());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("shows what the transform does and when to use it", async () => {
    const { container, unmount } = renderDialog();
    await act(async () => {});

    expect(api.transforms.getDocumentation).toHaveBeenCalledWith("domain_to_ip");
    expect(container.textContent).toContain("What it does");
    expect(container.textContent).toContain("Performs a DNS lookup of A and AAAA records.");
    expect(container.textContent).toContain("When to use it");
    expect(container.textContent).toContain("Use this first when pivoting");
    expect(container.textContent).toContain("Limitations");
    expect(container.textContent).toContain("Map a domain to its hosting infrastructure");
    unmount();
  });

  it("falls back to the short description and flags missing docs", async () => {
    vi.mocked(api.transforms.getDocumentation).mockResolvedValue(
      makeDoc({
        long_description: "",
        when_to_use: "",
        limitations: "",
        example_use_cases: [],
      }),
    );

    const { container, unmount } = renderDialog();
    await act(async () => {});

    expect(container.textContent).toContain("Resolves A and AAAA records for a domain");
    expect(container.textContent).not.toContain("When to use it");
    expect(container.textContent).toContain("has not published detailed documentation yet");
    unmount();
  });

  it("does not fetch documentation while closed", async () => {
    const { unmount } = renderDialog(false);
    await act(async () => {});

    expect(api.transforms.getDocumentation).not.toHaveBeenCalled();
    unmount();
  });

  it("warns that an unverified plugin can read the required API keys", async () => {
    vi.mocked(api.transforms.getDocumentation).mockResolvedValue(
      makeDoc({
        source: "plugin",
        plugin_name: "ip-to-shodan-host",
        plugin_verification_tier: "community",
        api_key_services: ["shodan"],
      }),
    );

    const { container, unmount } = renderDialog();
    await act(async () => {});

    expect(container.textContent).toContain("Needs an API key for: shodan");
    expect(container.textContent).toContain("will have access to");
    unmount();
  });
});
