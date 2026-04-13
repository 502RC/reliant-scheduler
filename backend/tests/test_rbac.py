"""Integration tests for the RBAC system.

Tests user management, workgroups, security policies, permission enforcement,
audit logging, and auth endpoints against a real PostgreSQL database.
All tests run in dev mode (no Entra ID) where the dev user is auto-created
as a Scheduler_Administrator.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from reliant_scheduler.models.user import (
    AuditLog,
    SecurityPolicy,
    User,
    UserRole,
    UserStatus,
    Workgroup,
    WorkgroupMember,
)


# ---------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------


class TestAuth:
    async def test_auth_me_returns_dev_user(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "dev@reliant.local"
        assert data["user"]["role"] == "scheduler_administrator"
        assert "admin:*" in data["permissions"]
        assert "read:*" in data["permissions"]

    async def test_auth_token_dev_mode(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/token",
            json={"authorization_code": "test", "redirect_uri": "http://localhost"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "dev-token"
        assert data["user"]["email"] == "dev@reliant.local"


# ---------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------


class TestUsers:
    async def test_create_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/users",
            json={
                "email": "alice@example.com",
                "display_name": "Alice",
                "role": "operator",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@example.com"
        assert data["role"] == "operator"
        assert data["status"] == "active"

    async def test_create_user_invalid_role(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/users",
            json={"email": "bad@example.com", "display_name": "Bad", "role": "superuser"},
        )
        assert resp.status_code == 400

    async def test_list_users(self, client: AsyncClient) -> None:
        await client.post(
            "/api/users",
            json={"email": "bob@example.com", "display_name": "Bob", "role": "inquiry"},
        )
        resp = await client.get("/api/users")
        assert resp.status_code == 200
        data = resp.json()
        # At least 1 user (bob) + the dev user
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_users_filter_by_role(self, client: AsyncClient) -> None:
        await client.post(
            "/api/users",
            json={"email": "carol@example.com", "display_name": "Carol", "role": "operator"},
        )
        resp = await client.get("/api/users?role=operator")
        assert resp.status_code == 200
        data = resp.json()
        assert all(u["role"] == "operator" for u in data["items"])

    async def test_get_user(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/users",
            json={"email": "dave@example.com", "display_name": "Dave", "role": "user"},
        )
        user_id = create_resp.json()["id"]
        resp = await client.get(f"/api/users/{user_id}")
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Dave"

    async def test_get_user_not_found(self, client: AsyncClient) -> None:
        resp = await client.get(f"/api/users/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_update_user(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/users",
            json={"email": "eve@example.com", "display_name": "Eve", "role": "inquiry"},
        )
        user_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/users/{user_id}",
            json={"role": "operator", "display_name": "Eve O."},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "operator"
        assert resp.json()["display_name"] == "Eve O."

    async def test_update_user_invalid_status(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/users",
            json={"email": "frank@example.com", "display_name": "Frank", "role": "inquiry"},
        )
        user_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/users/{user_id}",
            json={"status": "banned"},
        )
        assert resp.status_code == 400

    async def test_delete_user(self, client: AsyncClient) -> None:
        create_resp = await client.post(
            "/api/users",
            json={"email": "gone@example.com", "display_name": "Gone", "role": "inquiry"},
        )
        user_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/users/{user_id}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/users/{user_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------
# Workgroup CRUD
# ---------------------------------------------------------------


class TestWorkgroups:
    async def test_create_workgroup(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/workgroups",
            json={"name": "Engineering", "description": "Backend team"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Engineering"

    async def test_list_workgroups(self, client: AsyncClient) -> None:
        await client.post("/api/workgroups", json={"name": "Ops"})
        resp = await client.get("/api/workgroups")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_workgroup(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/workgroups", json={"name": "QA"})
        wg_id = create_resp.json()["id"]
        resp = await client.get(f"/api/workgroups/{wg_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "QA"

    async def test_update_workgroup(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/workgroups", json={"name": "Old Name"})
        wg_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/api/workgroups/{wg_id}", json={"name": "New Name"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_delete_workgroup(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/workgroups", json={"name": "Temp"})
        wg_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/workgroups/{wg_id}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/workgroups/{wg_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------
# Workgroup members
# ---------------------------------------------------------------


class TestWorkgroupMembers:
    async def _setup(self, client: AsyncClient) -> tuple[str, str]:
        """Create a workgroup and a user, return (workgroup_id, user_id)."""
        wg_resp = await client.post("/api/workgroups", json={"name": f"WG-{uuid.uuid4().hex[:6]}"})
        user_resp = await client.post(
            "/api/users",
            json={"email": f"{uuid.uuid4().hex[:6]}@test.com", "display_name": "Test", "role": "user"},
        )
        return wg_resp.json()["id"], user_resp.json()["id"]

    async def test_add_member(self, client: AsyncClient) -> None:
        wg_id, user_id = await self._setup(client)
        resp = await client.post(
            f"/api/workgroups/{wg_id}/members",
            json={"user_id": user_id, "role": "member"},
        )
        assert resp.status_code == 201
        assert resp.json()["user_id"] == user_id
        assert resp.json()["role"] == "member"

    async def test_add_member_duplicate(self, client: AsyncClient) -> None:
        wg_id, user_id = await self._setup(client)
        await client.post(
            f"/api/workgroups/{wg_id}/members",
            json={"user_id": user_id, "role": "member"},
        )
        resp = await client.post(
            f"/api/workgroups/{wg_id}/members",
            json={"user_id": user_id, "role": "admin"},
        )
        assert resp.status_code == 409

    async def test_list_members(self, client: AsyncClient) -> None:
        wg_id, user_id = await self._setup(client)
        await client.post(
            f"/api/workgroups/{wg_id}/members",
            json={"user_id": user_id, "role": "member"},
        )
        resp = await client.get(f"/api/workgroups/{wg_id}/members")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_remove_member(self, client: AsyncClient) -> None:
        wg_id, user_id = await self._setup(client)
        await client.post(
            f"/api/workgroups/{wg_id}/members",
            json={"user_id": user_id, "role": "member"},
        )
        resp = await client.delete(f"/api/workgroups/{wg_id}/members/{user_id}")
        assert resp.status_code == 204

    async def test_remove_nonexistent_member(self, client: AsyncClient) -> None:
        wg_id, _ = await self._setup(client)
        resp = await client.delete(f"/api/workgroups/{wg_id}/members/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------
# Security policies
# ---------------------------------------------------------------


class TestSecurityPolicies:
    async def test_create_policy(self, client: AsyncClient) -> None:
        user_resp = await client.post(
            "/api/users",
            json={"email": "poluser@example.com", "display_name": "Pol", "role": "inquiry"},
        )
        user_id = user_resp.json()["id"]
        resp = await client.post(
            "/api/security-policies",
            json={
                "name": "Allow read jobs",
                "resource_type": "job",
                "principal_type": "user",
                "principal_id": user_id,
                "permission": "read",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "job"
        assert data["permission"] == "read"

    async def test_create_policy_invalid_resource_type(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/security-policies",
            json={
                "name": "Bad",
                "resource_type": "unicorn",
                "principal_type": "user",
                "principal_id": str(uuid.uuid4()),
                "permission": "read",
            },
        )
        assert resp.status_code == 400

    async def test_create_policy_invalid_permission(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/security-policies",
            json={
                "name": "Bad",
                "resource_type": "job",
                "principal_type": "user",
                "principal_id": str(uuid.uuid4()),
                "permission": "destroy",
            },
        )
        assert resp.status_code == 400

    async def test_list_policies(self, client: AsyncClient) -> None:
        resp = await client.get("/api/security-policies")
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_get_policy(self, client: AsyncClient) -> None:
        user_resp = await client.post(
            "/api/users",
            json={"email": "polget@example.com", "display_name": "Pol2", "role": "inquiry"},
        )
        create_resp = await client.post(
            "/api/security-policies",
            json={
                "name": "Test policy",
                "resource_type": "schedule",
                "principal_type": "user",
                "principal_id": user_resp.json()["id"],
                "permission": "write",
            },
        )
        pol_id = create_resp.json()["id"]
        resp = await client.get(f"/api/security-policies/{pol_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test policy"

    async def test_delete_policy(self, client: AsyncClient) -> None:
        user_resp = await client.post(
            "/api/users",
            json={"email": "poldel@example.com", "display_name": "Pol3", "role": "inquiry"},
        )
        create_resp = await client.post(
            "/api/security-policies",
            json={
                "name": "To delete",
                "resource_type": "connection",
                "principal_type": "user",
                "principal_id": user_resp.json()["id"],
                "permission": "admin",
            },
        )
        pol_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/security-policies/{pol_id}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/security-policies/{pol_id}")
        assert resp.status_code == 404


# ---------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------


class TestAuditLog:
    async def test_query_audit_log(self, client: AsyncClient) -> None:
        resp = await client.get("/api/audit-log")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_audit_log_filters(self, client: AsyncClient) -> None:
        resp = await client.get("/api/audit-log?resource_type=user&action=create")
        assert resp.status_code == 200


# ---------------------------------------------------------------
# Permission enforcement (role-based)
# ---------------------------------------------------------------


class TestPermissionEnforcement:
    """Test that the role hierarchy controls access correctly.

    In dev mode the auto-created user is Scheduler_Administrator so
    all routes are accessible. These tests verify the permission
    enforcement logic by creating lower-privilege users and checking
    that the models/logic work correctly at the data layer.
    """

    async def test_role_hierarchy_values(self) -> None:
        from reliant_scheduler.models.user import role_level

        assert role_level(UserRole.SCHEDULER_ADMINISTRATOR) > role_level(UserRole.ADMINISTRATOR)
        assert role_level(UserRole.ADMINISTRATOR) > role_level(UserRole.SCHEDULER)
        assert role_level(UserRole.SCHEDULER) > role_level(UserRole.OPERATOR)
        assert role_level(UserRole.OPERATOR) > role_level(UserRole.USER)
        assert role_level(UserRole.USER) > role_level(UserRole.INQUIRY)

    async def test_role_permissions_mapping(self) -> None:
        from reliant_scheduler.api.permissions import _role_has_permission

        # Scheduler_Administrator has all permissions
        assert _role_has_permission(UserRole.SCHEDULER_ADMINISTRATOR, "read")
        assert _role_has_permission(UserRole.SCHEDULER_ADMINISTRATOR, "write")
        assert _role_has_permission(UserRole.SCHEDULER_ADMINISTRATOR, "execute")
        assert _role_has_permission(UserRole.SCHEDULER_ADMINISTRATOR, "admin")

        # Inquiry has only read
        assert _role_has_permission(UserRole.INQUIRY, "read")
        assert not _role_has_permission(UserRole.INQUIRY, "write")
        assert not _role_has_permission(UserRole.INQUIRY, "execute")
        assert not _role_has_permission(UserRole.INQUIRY, "admin")

        # Operator has read and execute
        assert _role_has_permission(UserRole.OPERATOR, "read")
        assert _role_has_permission(UserRole.OPERATOR, "execute")
        assert not _role_has_permission(UserRole.OPERATOR, "write")
        assert not _role_has_permission(UserRole.OPERATOR, "admin")

    async def test_security_policy_grant(self, db_session: AsyncSession) -> None:
        """Test that a security policy grants access to a specific resource."""
        from reliant_scheduler.api.permissions import _check_security_policies

        # Create an inquiry user
        user = User(
            email=f"inquiry-{uuid.uuid4().hex[:6]}@test.com",
            display_name="Inquiry User",
            role=UserRole.INQUIRY,
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
        await db_session.flush()

        # Without a policy, no write access
        has_access = await _check_security_policies(db_session, user, "job", "write")
        assert has_access is False

        # Add a policy granting write on all jobs
        policy = SecurityPolicy(
            name="Grant write jobs",
            resource_type="job",
            principal_type="user",
            principal_id=user.id,
            permission="write",
        )
        db_session.add(policy)
        await db_session.flush()

        has_access = await _check_security_policies(db_session, user, "job", "write")
        assert has_access is True

    async def test_workgroup_policy_grant(self, db_session: AsyncSession) -> None:
        """Test that workgroup membership inherits security policies."""
        from reliant_scheduler.api.permissions import _check_security_policies

        # Create user
        user = User(
            email=f"wguser-{uuid.uuid4().hex[:6]}@test.com",
            display_name="WG User",
            role=UserRole.INQUIRY,
            status=UserStatus.ACTIVE,
        )
        db_session.add(user)
        await db_session.flush()

        # Create workgroup and add user
        wg = Workgroup(name=f"TestWG-{uuid.uuid4().hex[:6]}")
        db_session.add(wg)
        await db_session.flush()

        member = WorkgroupMember(user_id=user.id, workgroup_id=wg.id, role="member")
        db_session.add(member)
        await db_session.flush()

        # Add a policy for the workgroup
        policy = SecurityPolicy(
            name="WG execute schedules",
            resource_type="schedule",
            principal_type="workgroup",
            principal_id=wg.id,
            permission="execute",
        )
        db_session.add(policy)
        await db_session.flush()

        # User should now have execute on schedule via workgroup
        has_access = await _check_security_policies(db_session, user, "schedule", "execute")
        assert has_access is True

        # But not write
        has_access = await _check_security_policies(db_session, user, "schedule", "write")
        assert has_access is False


# ---------------------------------------------------------------
# Audit log middleware (verify entries are written)
# ---------------------------------------------------------------


class TestAuditMiddleware:
    async def test_mutation_creates_audit_entry(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST to a mutating endpoint should create an audit_log entry."""
        # Create a user (mutating operation)
        resp = await client.post(
            "/api/users",
            json={
                "email": f"audit-test-{uuid.uuid4().hex[:6]}@example.com",
                "display_name": "Audit Test",
                "role": "inquiry",
            },
        )
        assert resp.status_code == 201

        # Check audit_log table for the entry
        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "user",
                AuditLog.action == "create",
            )
        )
        entries = result.scalars().all()
        # At least one audit entry for user creation
        assert len(entries) >= 1

    async def test_get_does_not_create_audit_entry(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET requests should not create audit log entries."""
        await client.get("/api/users")

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "read")
        )
        entries = result.scalars().all()
        assert len(entries) == 0
