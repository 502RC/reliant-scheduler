import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { securityPolicies } from "@/services/api";
import type { SecurityPolicyResponse } from "@/types/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";

const RESOURCE_TYPES = ["job", "schedule", "connection", "calendar", "environment"];
const PRINCIPAL_TYPES = ["user", "workgroup"];

export default function SecurityPoliciesList() {
  const [page, setPage] = useState(1);
  const [resourceFilter, setResourceFilter] = useState("");
  const [principalFilter, setPrincipalFilter] = useState("");

  const { data, loading, error } = useApi(
    () =>
      securityPolicies.list(
        page,
        50,
        resourceFilter || undefined,
        principalFilter || undefined
      ),
    [page, resourceFilter, principalFilter]
  );

  return (
    <div>
      <div className="page-header">
        <h2>Security Policies</h2>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={resourceFilter}
          onChange={(e) => { setResourceFilter(e.target.value); setPage(1); }}
          aria-label="Filter by resource type"
        >
          <option value="">All resources</option>
          {RESOURCE_TYPES.map((r) => (
            <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
          ))}
        </select>
        <select
          className="form-select"
          value={principalFilter}
          onChange={(e) => { setPrincipalFilter(e.target.value); setPage(1); }}
          aria-label="Filter by principal type"
        >
          <option value="">All principals</option>
          {PRINCIPAL_TYPES.map((p) => (
            <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
          ))}
        </select>
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load policies: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No security policies"
          description="Security policies grant granular permissions on specific resources."
        />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Resource</th>
                <th>Scope</th>
                <th>Principal</th>
                <th>Permission</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p: SecurityPolicyResponse) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>
                    <span className="trigger-type-badge">{p.resource_type}</span>
                  </td>
                  <td>{p.resource_id ? p.resource_id.slice(0, 8) + "..." : "All"}</td>
                  <td>
                    <span className="conn-type-badge conn-type-generic">
                      {p.principal_type}
                    </span>
                    <span style={{ marginLeft: 4, fontSize: 12, color: "#6b7280" }}>
                      {p.principal_id.slice(0, 8)}...
                    </span>
                  </td>
                  <td>
                    <span className="trigger-type-badge">{p.permission}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} polic{data.total !== 1 ? "ies" : "y"}</span>
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
