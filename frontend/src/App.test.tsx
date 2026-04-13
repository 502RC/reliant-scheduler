import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// Mock MSAL modules before importing App
vi.mock("@azure/msal-react", () => ({
  MsalProvider: ({ children }: { children: React.ReactNode }) => children,
  AuthenticatedTemplate: () => null,
  UnauthenticatedTemplate: ({ children }: { children: React.ReactNode }) => children,
  useMsal: () => ({ accounts: [], inProgress: "none" }),
  useIsAuthenticated: () => false,
}));

vi.mock("@/services/auth", () => ({
  msalInstance: {},
  initializeMsal: vi.fn().mockResolvedValue(undefined),
  loginRedirect: vi.fn(),
  logoutRedirect: vi.fn(),
  acquireAccessToken: vi.fn().mockResolvedValue(null),
  mapAccountToProfile: vi.fn(),
  msalConfig: {},
  loginRequest: {},
  tokenRequest: {},
  AUTH_DISABLED: false,
  MOCK_USER: {
    id: "dev-user",
    displayName: "Dev User",
    email: "dev@localhost",
    role: "admin",
    lastLogin: null,
  },
}));

import App from "./App";

describe("App", () => {
  it("renders the login page when unauthenticated", () => {
    render(<App />);
    expect(screen.getByText("Reliant Scheduler")).toBeInTheDocument();
    expect(
      screen.getByText("Sign in with Microsoft Entra ID")
    ).toBeInTheDocument();
  });
});
