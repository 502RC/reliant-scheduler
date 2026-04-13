import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

export default function Login() {
  const { login, isLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);

  // Check URL hash for MSAL error responses
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes("error=")) {
      const params = new URLSearchParams(hash.slice(1));
      const errorCode = params.get("error");
      const errorDesc = params.get("error_description");

      if (errorCode === "consent_required") {
        setError("Administrator consent is required for this application. Please contact your IT admin.");
      } else if (errorCode === "interaction_required") {
        setError("Additional authentication is required. Please try signing in again.");
      } else if (errorCode === "access_denied") {
        setError("Access was denied. Your account may not have permission to use this application.");
      } else if (errorDesc) {
        setError(errorDesc);
      }
    }
  }, []);

  if (isLoading) {
    return (
      <div className="login-page">
        <LoadingSpinner message="Authenticating..." />
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Reliant Scheduler</h1>
        <p>Enterprise workload automation platform</p>
        {error && (
          <div className="login-error" role="alert">
            {error}
          </div>
        )}
        <button className="login-sso-btn" onClick={login}>
          <svg width="20" height="20" viewBox="0 0 21 21" fill="none" aria-hidden>
            <rect width="9.5" height="9.5" fill="#f25022" />
            <rect x="11.5" width="9.5" height="9.5" fill="#7fba00" />
            <rect y="11.5" width="9.5" height="9.5" fill="#00a4ef" />
            <rect x="11.5" y="11.5" width="9.5" height="9.5" fill="#ffb900" />
          </svg>
          Sign in with Microsoft Entra ID
        </button>
      </div>
    </div>
  );
}
