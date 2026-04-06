import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import { AuthPage } from "./AuthPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const authState = {
  signIn: vi.fn<(email: string, password: string) => Promise<string | null>>(),
  signUp: vi.fn<(email: string, password: string) => Promise<string | null>>(),
  resetPassword: vi.fn<(email: string) => Promise<string | null>>(),
};

vi.mock("../stores/authStore", () => ({
  useAuthStore: () => authState,
}));

function renderAuth(mode: "signin" | "signup" | "forgot") {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<AuthPage mode={mode} />} />
          <Route path="/" element={<div>HOME</div>} />
        </Routes>
      </MemoryRouter>,
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

describe("AuthPage", () => {
  beforeEach(() => {
    authState.signIn.mockReset().mockResolvedValue(null);
    authState.signUp.mockReset().mockResolvedValue(null);
    authState.resetPassword.mockReset().mockResolvedValue(null);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("navigates to home after successful sign-in", async () => {
    const { container, unmount } = renderAuth("signin");
    const emailInput = container.querySelector("input[type='email']") as HTMLInputElement;
    const passwordInput = container.querySelector("input[type='password']") as HTMLInputElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setInputValue(emailInput, "user@example.com");
    await setInputValue(passwordInput, "secret123");
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(authState.signIn).toHaveBeenCalledWith("user@example.com", "secret123");
    expect(container.textContent).toContain("HOME");
    unmount();
  });

  it("shows error when sign-in fails", async () => {
    authState.signIn.mockResolvedValue("Invalid credentials");
    const { container, unmount } = renderAuth("signin");
    const emailInput = container.querySelector("input[type='email']") as HTMLInputElement;
    const passwordInput = container.querySelector("input[type='password']") as HTMLInputElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setInputValue(emailInput, "user@example.com");
    await setInputValue(passwordInput, "badpass");
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(container.textContent).toContain("Invalid credentials");
    unmount();
  });

  it("shows reset confirmation in forgot mode", async () => {
    const { container, unmount } = renderAuth("forgot");
    const emailInput = container.querySelector("input[type='email']") as HTMLInputElement;
    const form = container.querySelector("form") as HTMLFormElement;

    await setInputValue(emailInput, "user@example.com");
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(authState.resetPassword).toHaveBeenCalledWith("user@example.com");
    expect(container.textContent).toContain("Check your email for a password reset link.");
    unmount();
  });
});
