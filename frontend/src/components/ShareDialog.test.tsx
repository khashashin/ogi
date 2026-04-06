import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ShareDialog } from "./ShareDialog";
import { api } from "../api/client";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api/client", () => ({
  api: {
    members: {
      list: vi.fn(),
      add: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
    },
  },
}));

function renderDialog() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(<ShareDialog open={true} onClose={() => {}} projectId="p1" />);
  });

  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

async function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("ShareDialog", () => {
  beforeEach(() => {
    vi.mocked(api.members.list).mockReset().mockResolvedValue([]);
    vi.mocked(api.members.add).mockReset().mockResolvedValue({
      project_id: "p1",
      user_id: "u1",
      role: "editor",
      display_name: "",
      email: "invitee@example.com",
    });
    vi.mocked(api.members.update).mockReset();
    vi.mocked(api.members.remove).mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("loads members on open", async () => {
    const { container, unmount } = renderDialog();
    await act(async () => {});
    expect(api.members.list).toHaveBeenCalledWith("p1");
    expect(container.textContent).toContain("Share Project");
    unmount();
  });

  it("invites member via API", async () => {
    const { container, unmount } = renderDialog();
    await act(async () => {});

    const emailInput = container.querySelector("input[type='email']") as HTMLInputElement;
    const roleSelect = container.querySelector("select") as HTMLSelectElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setInputValue(emailInput, "invitee@example.com");
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
      setter?.call(roleSelect, "viewer");
      roleSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(api.members.add).toHaveBeenCalledWith("p1", {
      email: "invitee@example.com",
      role: "viewer",
    });
    unmount();
  });
});
