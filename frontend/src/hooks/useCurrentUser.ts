import { useState, useEffect, useCallback, useRef } from "react";
import { auth } from "@/services/api";
import { useAuth } from "@/hooks/useAuth";
import type { UserMeResponse, UserProfile } from "@/types/api";
import { AUTH_DISABLED, MOCK_USER } from "@/services/auth";

interface CurrentUserState {
  /** Merged profile: MSAL account info enriched with backend data when available */
  user: UserProfile | null;
  /** Full backend response (null if backend unavailable or dev mode) */
  backendUser: UserMeResponse | null;
  /** Whether the backend /auth/me call is in progress */
  isLoadingBackend: boolean;
  /** Error from backend call (null if successful or not attempted) */
  backendError: string | null;
  /** Re-fetch backend user data */
  refetch: () => void;
}

/**
 * Hook that combines MSAL account info with backend /api/auth/me data.
 * Gracefully degrades: if the backend is unavailable, falls back to
 * MSAL-only profile (or mock user in dev mode).
 */
export function useCurrentUser(): CurrentUserState {
  const { user: msalUser } = useAuth();
  const [backendUser, setBackendUser] = useState<UserMeResponse | null>(null);
  const [isLoadingBackend, setIsLoadingBackend] = useState(!AUTH_DISABLED);
  const [backendError, setBackendError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchBackendUser = useCallback(async () => {
    if (AUTH_DISABLED) return;

    setIsLoadingBackend(true);
    setBackendError(null);
    try {
      const response = await auth.me();
      if (mountedRef.current) {
        setBackendUser(response);
      }
    } catch {
      if (mountedRef.current) {
        // Graceful degradation: backend not available, use MSAL-only profile
        setBackendError("Backend user endpoint unavailable");
      }
    } finally {
      if (mountedRef.current) {
        setIsLoadingBackend(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchBackendUser();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchBackendUser]);

  // Merge backend data into MSAL profile when available
  const user: UserProfile | null = AUTH_DISABLED
    ? MOCK_USER
    : backendUser
      ? {
          id: backendUser.user.id,
          displayName: backendUser.user.display_name,
          email: backendUser.user.email,
          role: backendUser.user.role as UserProfile["role"],
          lastLogin: backendUser.user.last_login_at,
        }
      : msalUser;

  return {
    user,
    backendUser,
    isLoadingBackend,
    backendError,
    refetch: fetchBackendUser,
  };
}
