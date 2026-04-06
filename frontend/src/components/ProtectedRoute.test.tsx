import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import { ProtectedRoute } from "./ProtectedRoute";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const authState = {
  authEnabled: true,
  user: null as { id: string } | null,
  loading: false,
  isRecovery: false,
  initialize: vi.fn(),
};

vi.mock("../stores/authStore", () => ({
  useAuthStore: (selector?: (state: typeof authState) => unknown) =>
    selector ? selector(authState) : authState,
}));

function renderWithRouter(initialPath: string) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root: Root = createRoot(container);

  act(() => {
    root.render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>HOME</div>} />
          </Route>
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route path="/reset-password" element={<div>RESET</div>} />
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

describe("ProtectedRoute", () => {
  beforeEach(() => {
    authState.authEnabled = true;
    authState.user = null;
    authState.loading = false;
    authState.isRecovery = false;
    authState.initialize.mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("passes through when auth is disabled (local mode)", () => {
    authState.authEnabled = false;
    const { container, unmount } = renderWithRouter("/");
    expect(container.textContent).toContain("HOME");
    expect(authState.initialize).toHaveBeenCalledTimes(1);
    unmount();
  });

  it("redirects to login when auth enabled and user is missing", async () => {
    const { container, unmount } = renderWithRouter("/");
    await act(async () => {});
    expect(container.textContent).toContain("LOGIN");
    unmount();
  });

  it("redirects to reset-password in recovery mode", async () => {
    authState.user = { id: "u1" };
    authState.isRecovery = true;
    const { container, unmount } = renderWithRouter("/");
    await act(async () => {});
    expect(container.textContent).toContain("RESET");
    unmount();
  });
});
