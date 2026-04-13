import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { credentials } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import StatusBadge from "@/components/shared/StatusBadge";
import { formatDateTime } from "@/utils/format";

const CREDENTIAL_TYPE_LABELS: Record<string, string> = {
  windows_ad: "Windows / AD",
  ssh_password: "SSH Password",
  ssh_private_key: "SSH Private Key",
  api_key: "API Key",
  api_key_secret: "API Key + Secret",
  bearer_token: "Bearer Token",
  oauth2_client: "OAuth2 Client",
  database: "Database",
  smtp: "SMTP",
  azure_service_principal: "Azure SP",
  certificate: "Certificate",
  custom: "Custom",
};

export default function CredentialsList() {
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  const result = useApi(
    () => credentials.list(page, 50, typeFilter || undefined),
    [page, typeFilter]
  );

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete credential "${name}"? This cannot be undone.`)) return;
    setDeleting(id);
    try {
      await credentials.delete(id);
      result.refetch();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete credential";
      alert(msg);
    } finally {
      setDeleting(null);
    }
  }

  if (result.loading) return <LoadingSpinner message="Loading credentials..." />;

  const data = result.data;
  const items = data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Credentials</h2>
        {hasRole("admin", "scheduler_admin") && (
          <Link to="/credentials/new" className="btn btn-primary">
            + New Credential
          </Link>
        )}
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <select
            className="form-select"
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            aria-label="Filter by type"
            style={{ maxWidth: 200 }}
          >
            <option value="">All types</option>
            {Object.entries(CREDENTIAL_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        {result.error ? (
          <div className="form-error" style={{ padding: 12 }}>{result.error}</div>
        ) : items.length === 0 ? (
          <p style={{ color: "#6b7280", padding: 24, textAlign: "center" }}>
            No credentials found. Create one to store connection secrets securely.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Description</th>
                <th>Secrets</th>
                <th>Used By</th>
                <th>Created</th>
                {hasRole("admin", "scheduler_admin") && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((cred) => (
                <tr key={cred.id}>
                  <td>
                    <Link to={`/credentials/${cred.id}/edit`} className="link">
                      {cred.name}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={CREDENTIAL_TYPE_LABELS[cred.credential_type] ?? cred.credential_type} variant="info" />
                  </td>
                  <td style={{ color: "#6b7280", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {cred.description || "—"}
                  </td>
                  <td>
                    {cred.secret_fields.length > 0 ? (
                      <span style={{ color: "#6b7280", fontSize: 12 }}>
                        {cred.secret_fields.length} field{cred.secret_fields.length > 1 ? "s" : ""} in Key Vault
                      </span>
                    ) : "—"}
                  </td>
                  <td>
                    {cred.usage_count > 0 ? (
                      <span>{cred.usage_count} connection{cred.usage_count > 1 ? "s" : ""}</span>
                    ) : (
                      <span style={{ color: "#9ca3af" }}>unused</span>
                    )}
                  </td>
                  <td>{formatDateTime(cred.created_at)}</td>
                  {hasRole("admin", "scheduler_admin") && (
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        <Link to={`/credentials/${cred.id}/edit`} className="btn btn-secondary btn-sm">
                          Edit
                        </Link>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(cred.id, cred.name)}
                          disabled={deleting === cred.id}
                        >
                          {deleting === cred.id ? "..." : "Delete"}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data && data.pages > 1 && (
          <div className="pagination" style={{ marginTop: 16 }}>
            {Array.from({ length: data.pages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                className={p === page ? "active" : ""}
                onClick={() => setPage(p)}
              >
                {p}
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
