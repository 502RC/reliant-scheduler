import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/hooks/useAuth";

interface AuthError {
  title: string;
  message: string;
  action?: "reauthenticate" | "dismiss";
}

/**
 * Listens for auth-related errors and shows a toast notification.
 * Handles: token expiry, consent required, admin approval needed, account disabled.
 */
export default function AuthErrorToast() {
  const { login } = useAuth();
  const [error, setError] = useState<AuthError | null>(null);

  // Listen for custom auth error events dispatched by the API client
  useEffect(() => {
    function handleAuthError(event: CustomEvent<AuthError>) {
      setError(event.detail);
    }

    window.addEventListener(
      "reliant:auth-error",
      handleAuthError as EventListener
    );
    return () => {
      window.removeEventListener(
        "reliant:auth-error",
        handleAuthError as EventListener
      );
    };
  }, []);

  const dismiss = useCallback(() => setError(null), []);

  const reauthenticate = useCallback(async () => {
    setError(null);
    await login();
  }, [login]);

  if (!error) return null;

  return (
    <div className="auth-toast" role="alert" aria-live="assertive">
      <svg
        className="auth-toast-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div className="auth-toast-content">
        <div className="auth-toast-title">{error.title}</div>
        <div className="auth-toast-message">{error.message}</div>
        {error.action === "reauthenticate" && (
          <button className="auth-toast-action" onClick={reauthenticate}>
            Re-authenticate
          </button>
        )}
      </div>
      <button
        className="auth-toast-close"
        onClick={dismiss}
        aria-label="Dismiss notification"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}

/**
 * Dispatch an auth error event. Call this from the API client or auth service
 * when authentication issues are detected.
 */
export function dispatchAuthError(
  title: string,
  message: string,
  action?: "reauthenticate" | "dismiss"
): void {
  window.dispatchEvent(
    new CustomEvent("reliant:auth-error", {
      detail: { title, message, action },
    })
  );
}
