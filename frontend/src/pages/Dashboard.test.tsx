import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

vi.mock("@azure/msal-react", () => ({
  useMsal: () => ({ accounts: [], inProgress: "none" }),
  useIsAuthenticated: () => true,
}));

vi.mock("@/services/auth", () => ({
  acquireAccessToken: vi.fn().mockResolvedValue(null),
  mapAccountToProfile: vi.fn().mockReturnValue({
    id: "1",
    displayName: "Test User",
    email: "test@example.com",
    role: "admin",
    lastLogin: null,
  }),
  loginRedirect: vi.fn(),
  logoutRedirect: vi.fn(),
  AUTH_DISABLED: true,
}));

vi.mock("@/services/api", () => ({
  jobs: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 }),
  },
  agents: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, pages: 0 }),
  },
}));

import Dashboard from "./Dashboard";
import { EventBusProvider } from "@/services/eventBus";

describe("Dashboard", () => {
  it("renders the dashboard heading", async () => {
    render(
      <MemoryRouter>
        <EventBusProvider>
          <Dashboard />
        </EventBusProvider>
      </MemoryRouter>
    );
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
  });
});
