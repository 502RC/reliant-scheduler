import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { users } from "@/services/api";
import type { UserResponse_Admin } from "@/types/api";
import StatusBadge from "@/components/shared/StatusBadge";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";

const ROLES = [
  "scheduler_administrator",
  "administrator",
  "scheduler",
  "operator",
  "user",
  "inquiry",
];

export default function UsersList() {
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const { data, loading, error } = useApi(
    () => users.list(page, 50, roleFilter || undefined, statusFilter || undefined),
    [page, roleFilter, statusFilter]
  );

  return (
    <div>
      <div className="page-header">
        <h2>Users</h2>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
          aria-label="Filter by role"
        >
          <option value="">All roles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
          ))}
        </select>
        <select
          className="form-select"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load users: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState title="No users" description="No users match the current filters." />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Login</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u: UserResponse_Admin) => (
                <tr key={u.id}>
                  <td>{u.display_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className="trigger-type-badge">
                      {u.role.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td>
                    <StatusBadge
                      status={u.status}
                      variant={u.status === "active" ? "success" : "default"}
                    />
                  </td>
                  <td>{formatDateTime(u.last_login_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} user{data.total !== 1 ? "s" : ""}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page} of {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
