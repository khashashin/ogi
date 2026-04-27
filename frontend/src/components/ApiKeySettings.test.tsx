import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { ApiKeySettings } from "./ApiKeySettings";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api/client", () => ({
  api: {
    apiKeys: {
      list: vi.fn(),
      save: vi.fn(),
      delete: vi.fn(),
    },
  },
}));

function renderDialog(initialService?: string) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(
      <ApiKeySettings
        open={true}
        onClose={() => {}}
        initialService={initialService}
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

async function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function setSelectValue(select: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

describe("ApiKeySettings", () => {
  beforeEach(() => {
    vi.mocked(api.apiKeys.list).mockReset().mockResolvedValue([
      { service_name: "openai" },
    ]);
    vi.mocked(api.apiKeys.save).mockReset().mockResolvedValue({
      service_name: "gemini",
    });
    vi.mocked(api.apiKeys.delete).mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("does not allow adding another key for a configured service", async () => {
    const { container, unmount } = renderDialog("openai");
    await act(async () => {});

    const select = container.querySelector("select") as HTMLSelectElement;
    const openaiOption = Array.from(select.options).find(
      (option) => option.value === "openai",
    );
    expect(openaiOption?.disabled).toBe(true);
    expect(container.textContent).toContain("openai already has an API key");

    const passwordInput = container.querySelector("input[type='password']") as HTMLInputElement;
    const submitButton = container.querySelector("button[type='submit']") as HTMLButtonElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setInputValue(passwordInput, "sk-test");
    expect(submitButton.disabled).toBe(true);
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(api.apiKeys.save).not.toHaveBeenCalled();
    unmount();
  });

  it("saves a key for an unconfigured service", async () => {
    const { container, unmount } = renderDialog();
    await act(async () => {});

    const select = container.querySelector("select") as HTMLSelectElement;
    const passwordInput = container.querySelector("input[type='password']") as HTMLInputElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setSelectValue(select, "gemini");
    await setInputValue(passwordInput, "gm-test");
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(api.apiKeys.save).toHaveBeenCalledWith("gemini", "gm-test");
    unmount();
  });
});
