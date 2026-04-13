import { type ReactNode } from "react";
import {
  AuthenticatedTemplate,
  UnauthenticatedTemplate,
} from "@azure/msal-react";

interface ProtectedRouteProps {
  children: ReactNode;
  fallback: ReactNode;
}

export default function ProtectedRoute({
  children,
  fallback,
}: ProtectedRouteProps) {
  return (
    <>
      <AuthenticatedTemplate>{children}</AuthenticatedTemplate>
      <UnauthenticatedTemplate>{fallback}</UnauthenticatedTemplate>
    </>
  );
}
