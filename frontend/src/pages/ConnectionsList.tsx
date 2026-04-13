import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { connections } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";

const CONNECTION_TYPE_LABELS: Record<string, string> = {
  database: "Database (JDBC)",
  rest_api: "REST / WebService",
  sftp: "SSH / SFTP",
  azure_blob: "Azure Blob Storage",
  azure_servicebus: "Azure Service Bus",
  azure_eventhub: "Azure Event Hubs",
  custom: "Custom",
};

function connectionTypeLabel(type: string): string {
  return CONNECTION_TYPE_LABELS[type] ?? type;
}

export default function ConnectionsList() {
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");

  const { data, loading, error, refetch } = useApi(
    () => connections.list(page, 20, typeFilter || undefined),
    [page, typeFilter]
  );

  async function handleDelete(id: string) {
    if (!confirm("Delete this connection?")) return;
    try {
      await connections.delete(id);
      refetch();
    } catch {
      alert("Failed to delete connection");
    }
  }

  if (loading) return <LoadingSpinner message="Loading connections..." />;
  if (error) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        Failed to load connections: {error}
        <button className="btn btn-secondary btn-sm" style={{ marginLeft: 12 }} onClick={refetch}>
          Retry
        </button>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Connections</h2>
        {hasRole("admin") && (
          <Link to="/connections/new" className="btn btn-primary">
            + New Connection
          </Link>
        )}
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by connection type"
        >
          <option value="">All Types</option>
          {Object.entries(CONNECTION_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No connections"
          description="Connections define external system endpoints for jobs."
          action={
            hasRole("admin") ? (
              <Link to="/connections/new" className="btn btn-primary">
                New Connection
              </Link>
            ) : undefined
          }
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Connections">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Host</th>
                <th>Port</th>
                <th>Description</th>
                <th>Created</th>
                {hasRole("admin") && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 500 }}>{c.name}</td>
                  <td>
                    <span className={`conn-type-badge conn-type-${c.connection_type.startsWith("azure_") ? "azure" : "generic"}`}>
                      {connectionTypeLabel(c.connection_type)}
                    </span>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{c.host ?? "—"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{c.port ?? "—"}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {c.description ?? "—"}
                  </td>
                  <td>{formatDateTime(c.created_at)}</td>
                  {hasRole("admin") && (
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <Link to={`/connections/${c.id}/edit`} className="btn btn-secondary btn-sm">
                          Edit
                        </Link>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(c.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.pages > 1 && (
            <div className="data-table-footer">
              <span>Page {data.page} of {data.pages} ({data.total} total)</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
                <button disabled={page >= (data?.pages ?? 1)} onClick={() => setPage((p) => p + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
