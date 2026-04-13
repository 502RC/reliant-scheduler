import {
  PublicClientApplication,
  Configuration,
  LogLevel,
  AccountInfo,
  AuthenticationResult,
  SilentRequest,
  RedirectRequest,
  InteractionRequiredAuthError,
  BrowserAuthError,
} from "@azure/msal-browser";
import type { UserRole, UserProfile } from "@/types/api";

export const AUTH_DISABLED =
  import.meta.env.VITE_AUTH_DISABLED === "true";

const CLIENT_ID = import.meta.env.VITE_AZURE_CLIENT_ID ?? "";
const AUTHORITY =
  import.meta.env.VITE_AZURE_AUTHORITY ??
  "https://login.microsoftonline.com/common";
const REDIRECT_URI =
  import.meta.env.VITE_AZURE_REDIRECT_URI ?? window.location.origin;
const API_SCOPE =
  import.meta.env.VITE_API_SCOPE ?? `api://${CLIENT_ID}/access_as_user`;

const RETURN_URL_KEY = "reliant_return_url";

export const msalConfig: Configuration = {
  auth: {
    clientId: CLIENT_ID,
    authority: AUTHORITY,
    redirectUri: REDIRECT_URI,
    postLogoutRedirectUri: REDIRECT_URI,
  },
  cache: {
    cacheLocation: "localStorage",
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      loggerCallback: (_level: LogLevel, message: string) => {
        console.debug("[MSAL]", message);
      },
    },
  },
};

export const loginRequest: RedirectRequest = {
  scopes: [API_SCOPE, "openid", "profile", "email"],
};

export const tokenRequest: SilentRequest = {
  scopes: [API_SCOPE],
  account: undefined as unknown as AccountInfo,
};

export const msalInstance = new PublicClientApplication(msalConfig);

/** Mock user for dev mode when VITE_AUTH_DISABLED=true */
export const MOCK_USER: UserProfile = {
  id: "dev-user",
  displayName: "Dev User",
  email: "dev@localhost",
  role: "admin",
  lastLogin: null,
};

export async function initializeMsal(): Promise<void> {
  if (AUTH_DISABLED) return;

  await msalInstance.initialize();
  const response = await msalInstance.handleRedirectPromise();
  if (response) {
    msalInstance.setActiveAccount(response.account);
    // Restore the URL the user was trying to reach before login
    const returnUrl = sessionStorage.getItem(RETURN_URL_KEY);
    if (returnUrl) {
      sessionStorage.removeItem(RETURN_URL_KEY);
      window.history.replaceState(null, "", returnUrl);
    }
  } else {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }
}

export async function acquireAccessToken(): Promise<string | null> {
  if (AUTH_DISABLED) return "dev-token";

  const account = msalInstance.getActiveAccount();
  if (!account) return null;

  try {
    const response: AuthenticationResult =
      await msalInstance.acquireTokenSilent({
        ...tokenRequest,
        account,
      });
    return response.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      const suberror = error.subError ?? "";
      if (suberror === "consent_required") {
        dispatchAuthErrorEvent(
          "Consent Required",
          "Your administrator needs to grant consent for this application.",
          "reauthenticate"
        );
      } else if (suberror === "interaction_required") {
        dispatchAuthErrorEvent(
          "Re-authentication Required",
          "Your session requires interaction. Please sign in again.",
          "reauthenticate"
        );
      } else {
        // Generic interaction required — redirect
        dispatchAuthErrorEvent(
          "Session Expired",
          "Your session has expired. Redirecting to sign in.",
          "reauthenticate"
        );
      }
      await msalInstance.acquireTokenRedirect(loginRequest);
      return null;
    }
    if (error instanceof BrowserAuthError) {
      dispatchAuthErrorEvent(
        "Authentication Error",
        "A browser authentication error occurred. Please try signing in again.",
        "reauthenticate"
      );
      await msalInstance.acquireTokenRedirect(loginRequest);
      return null;
    }
    // Unknown error — don't silently swallow
    console.error("[Auth] Token acquisition failed:", error);
    throw error;
  }
}

export function getActiveAccount(): AccountInfo | null {
  if (AUTH_DISABLED) return null;
  return msalInstance.getActiveAccount();
}

export function mapAccountToProfile(account: AccountInfo): UserProfile {
  const claims = account.idTokenClaims as Record<string, unknown> | undefined;
  const roles = (claims?.roles as string[]) ?? [];

  let role: UserRole = "inquiry";
  if (roles.includes("Admin") || roles.includes("admin")) role = "admin";
  else if (
    roles.includes("Scheduler_Administrator") ||
    roles.includes("scheduler_admin")
  )
    role = "scheduler_admin";
  else if (roles.includes("Operator") || roles.includes("operator"))
    role = "operator";
  else if (roles.includes("Scheduler") || roles.includes("scheduler"))
    role = "scheduler";
  else if (roles.includes("User") || roles.includes("user")) role = "user";

  return {
    id: account.localAccountId,
    displayName: account.name ?? account.username,
    email: account.username,
    role,
    lastLogin: null,
  };
}

export async function loginRedirect(): Promise<void> {
  if (AUTH_DISABLED) return;
  // Save the current URL so we can restore it after login
  sessionStorage.setItem(RETURN_URL_KEY, window.location.pathname + window.location.search);
  await msalInstance.loginRedirect(loginRequest);
}

export async function logoutRedirect(): Promise<void> {
  if (AUTH_DISABLED) {
    window.location.reload();
    return;
  }
  await msalInstance.logoutRedirect({
    postLogoutRedirectUri: REDIRECT_URI,
  });
}

/** Dispatch a custom event for the AuthErrorToast component to display */
function dispatchAuthErrorEvent(
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
