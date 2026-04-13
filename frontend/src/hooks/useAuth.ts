import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { useCallback, useMemo } from "react";
import type { UserProfile, UserRole } from "@/types/api";
import {
  AUTH_DISABLED,
  MOCK_USER,
  loginRedirect,
  logoutRedirect,
  mapAccountToProfile,
} from "@/services/auth";

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserProfile | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: UserRole[]) => boolean;
}

/**
 * Primary auth hook. When VITE_AUTH_DISABLED=true, returns mock admin user
 * without touching MSAL. Use `useAuthMsal` for the MSAL-backed version.
 */
export function useAuth(): AuthState {
  if (AUTH_DISABLED) {
    return useAuthDev();
  }
  return useAuthMsal();
}

/** Dev mode auth — always authenticated with full access */
function useAuthDev(): AuthState {
  const login = useCallback(async () => { await loginRedirect(); }, []);
  const logout = useCallback(async () => { await logoutRedirect(); }, []);
  const hasRole = useCallback(() => true, []);

  return {
    isAuthenticated: true,
    isLoading: false,
    user: MOCK_USER,
    login,
    logout,
    hasRole,
  };
}

/** Production auth backed by MSAL */
function useAuthMsal(): AuthState {
  const { accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const isLoading = inProgress !== "none";

  const user = useMemo<UserProfile | null>(() => {
    if (accounts.length === 0) return null;
    return mapAccountToProfile(accounts[0]);
  }, [accounts]);

  const login = useCallback(async () => {
    await loginRedirect();
  }, []);

  const logout = useCallback(async () => {
    await logoutRedirect();
  }, []);

  const hasRole = useCallback(
    (...roles: UserRole[]) => {
      if (!user) return false;
      if (user.role === "admin" || user.role === "scheduler_admin") return true;
      return roles.includes(user.role);
    },
    [user]
  );

  return { isAuthenticated, isLoading, user, login, logout, hasRole };
}
