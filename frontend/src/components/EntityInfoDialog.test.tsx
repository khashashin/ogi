import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { EntityInfoDialog } from "./EntityInfoDialog";
import { EntityType } from "../types/entity";
import type { EntityTypeDocumentation } from "../types/entity";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api/client", () => ({
  api: {
    transforms: {
      entityTypeDocumentation: vi.fn(),
    },
  },
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

function makeDoc(overrides: Partial<EntityTypeDocumentation> = {}): EntityTypeDocumentation {
  return {
    type: EntityType.Domain,
    category: "Infrastructure",
    icon: "globe",
    color: "#22d3ee",
    description: "A registered domain name such as example.com.",
    usage: "One of the most productive starting points in OSINT.",
    consumed_by: [
      {
        name: "domain_to_ip",
        display_name: "Domain to IP Address",
        description: "Resolves A and AAAA records for a domain",
        category: "DNS",
        api_key_services: [],
        plugin_name: null,
      },
      {
        name: "ip_to_shodan_host",
        display_name: "IP to Shodan Host",
        description: "Creates a baseline Shodan host summary",
        category: "ip",
        api_key_services: ["shodan"],
        plugin_name: "ip-to-shodan-host",
      },
    ],
    produced_by: [
      {
        name: "ip_to_domain",
        display_name: "IP to Domain (Reverse DNS)",
        description: "Resolves PTR records for an IP address",
        category: "DNS",
        api_key_services: [],
        plugin_name: null,
      },
    ],
    ...overrides,
  };
}

function renderDialog(open = true, valueHint?: string) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(
      <EntityInfoDialog
        open={open}
        entityType={EntityType.Domain}
        valueHint={valueHint}
        onClose={() => {}}
      />,
    );
  });

  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe("EntityInfoDialog", () => {
  beforeEach(() => {
    vi.mocked(api.transforms.entityTypeDocumentation).mockReset().mockResolvedValue(makeDoc());
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("explains the entity type and lists transforms in both directions", async () => {
    const { container, unmount } = renderDialog();
    await act(async () => {});

    expect(api.transforms.entityTypeDocumentation).toHaveBeenCalledWith("Domain");
    expect(container.textContent).toContain("What it represents");
    expect(container.textContent).toContain("A registered domain name");
    expect(container.textContent).toContain("When to use it");

    expect(container.textContent).toContain("Transforms you can run on it (2)");
    expect(container.textContent).toContain("Domain to IP Address");
    expect(container.textContent).toContain("Requires API key: shodan");

    expect(container.textContent).toContain("Transforms that discover it (1)");
    expect(container.textContent).toContain("IP to Domain (Reverse DNS)");
    unmount();
  });

  it("shows the expected value hint when one is supplied", async () => {
    const { container, unmount } = renderDialog(true, "Enter domain, e.g. example.com");
    await act(async () => {});

    expect(container.textContent).toContain("Expected value");
    expect(container.textContent).toContain("Enter domain, e.g. example.com");
    unmount();
  });

  it("handles an entity type no transform accepts", async () => {
    vi.mocked(api.transforms.entityTypeDocumentation).mockResolvedValue(
      makeDoc({ consumed_by: [], produced_by: [] }),
    );

    const { container, unmount } = renderDialog();
    await act(async () => {});

    expect(container.textContent).toContain("Transforms you can run on it (0)");
    expect(container.textContent).toContain("No transform currently accepts this entity type");
    // The discovery section is hidden entirely rather than shown empty.
    expect(container.textContent).not.toContain("Transforms that discover it");
    unmount();
  });

  it("does not fetch while closed", async () => {
    const { unmount } = renderDialog(false);
    await act(async () => {});

    expect(api.transforms.entityTypeDocumentation).not.toHaveBeenCalled();
    unmount();
  });
});
