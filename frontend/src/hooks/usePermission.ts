import { useMemo } from "react";
import { useAuth } from "@/hooks/useAuth";
import { AUTH_DISABLED } from "@/services/auth";
import type { UserRole, PermissionCheck } from "@/types/api";

/**
 * Role-to-permission mapping.
 * Admin and scheduler_admin have full access (handled separately).
 * Other roles get specific permissions.
 */
const ROLE_PERMISSIONS: Record<UserRole, Set<PermissionCheck>> = {
  admin: new Set(["*:*"]),
  scheduler_admin: new Set(["*:*"]),
  scheduler: new Set([
    "job:read",
    "job:write",
    "schedule:read",
    "schedule:write",
    "environment:read",
    "connection:read",
    "agent:read",
    "dashboard:read",
  ]),
  operator: new Set([
    "job:read",
    "job:execute",
    "schedule:read",
    "environment:read",
    "connection:read",
    "agent:read",
    "dashboard:read",
  ]),
  user: new Set([
    "job:read",
    "job:write",
    "schedule:read",
    "environment:read",
    "connection:read",
    "agent:read",
    "dashboard:read",
  ]),
  inquiry: new Set([
    "job:read",
    "schedule:read",
    "environment:read",
    "connection:read",
    "agent:read",
    "dashboard:read",
  ]),
};

/**
 * Check if a user with the given role has a specific permission.
 * Format: "resource:action" (e.g., "job:write", "schedule:admin")
 */
function roleHasPermission(role: UserRole, permission: PermissionCheck): boolean {
  const perms = ROLE_PERMISSIONS[role];
  if (perms.has("*:*")) return true;

  if (perms.has(permission)) return true;

  // Check wildcard on resource (e.g., "job:*")
  const [resource] = permission.split(":");
  if (perms.has(`${resource}:*` as PermissionCheck)) return true;

  return false;
}

/**
 * Hook for RBAC-aware conditional rendering.
 *
 * @param resourceType - The resource type (e.g., "job", "schedule", "agent")
 * @param action - The action (e.g., "read", "write", "admin", "execute")
 * @returns Whether the current user has the requested permission
 *
 * @example
 * const canCreateJob = usePermission("job", "write");
 * const canDeleteJob = usePermission("job", "admin");
 * const isAdmin = usePermission("settings", "admin");
 */
export function usePermission(resourceType: string, action: string): boolean {
  const { user } = useAuth();

  return useMemo(() => {
    // Dev mode: full access
    if (AUTH_DISABLED) return true;

    // No user: no permissions
    if (!user) return false;

    return roleHasPermission(user.role, `${resourceType}:${action}` as PermissionCheck);
  }, [user, resourceType, action]);
}

/**
 * Hook that returns a permission checker function.
 * Useful when you need to check multiple permissions in one component.
 *
 * @example
 * const can = usePermissions();
 * if (can("job", "write")) { ... }
 * if (can("schedule", "admin")) { ... }
 */
export function usePermissions(): (resourceType: string, action: string) => boolean {
  const { user } = useAuth();

  return useMemo(() => {
    if (AUTH_DISABLED) return () => true;
    if (!user) return () => false;

    return (resourceType: string, action: string) =>
      roleHasPermission(user.role, `${resourceType}:${action}` as PermissionCheck);
  }, [user]);
}
