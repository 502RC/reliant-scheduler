import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { environments } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";
import type { EnvironmentCreate } from "@/types/api";

export default function EnvironmentsList() {
  const { hasRole } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createProd, setCreateProd] = useState(false);
  const [createVars, setCreateVars] = useState("");
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const { data, loading, error, refetch } = useApi(
    () => environments.list(page),
    [page]
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setSaving(true);

    let parsedVars: Record<string, string> | null = null;
    if (createVars.trim()) {
      try {
        parsedVars = JSON.parse(createVars);
      } catch {
        setCreateError("Variables must be valid JSON");
        setSaving(false);
        return;
      }
    }

    try {
      const data: EnvironmentCreate = {
        name: createName,
        description: createDesc || null,
        is_production: createProd,
        variables: parsedVars,
      };
      await environments.create(data);
      setShowCreate(false);
      setCreateName("");
      setCreateDesc("");
      setCreateProd(false);
      setCreateVars("");
      refetch();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create environment");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this environment?")) return;
    try {
      await environments.delete(id);
      refetch();
    } catch {
      alert("Failed to delete environment");
    }
  }

  if (loading) return <LoadingSpinner message="Loading environments..." />;
  if (error) {
    return (
      <div role="alert" className="card" style={{ color: "#dc2626" }}>
        Failed to load environments: {error}
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
        <h2>Environments</h2>
        {hasRole("admin") && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Environment
          </button>
        )}
      </div>

      {showCreate && (
        <div className="card" style={{ padding: 20, marginBottom: 16, maxWidth: 480 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>New Environment</h3>
          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label className="form-label" htmlFor="envName">Name *</label>
              <input
                id="envName"
                className="form-input"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                required
                placeholder="e.g. production, staging, dev"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="envDesc">Description</label>
              <input
                id="envDesc"
                className="form-input"
                value={createDesc}
                onChange={(e) => setCreateDesc(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="envVars">Variables (JSON)</label>
              <textarea
                id="envVars"
                className="form-textarea"
                style={{ fontFamily: "monospace" }}
                value={createVars}
                onChange={(e) => setCreateVars(e.target.value)}
                placeholder='{"DB_HOST": "...", "REGION": "eastus2"}'
              />
            </div>
            <div className="form-group">
              <label className="form-label">
                <input
                  type="checkbox"
                  checked={createProd}
                  onChange={(e) => setCreateProd(e.target.checked)}
                  style={{ marginRight: 8 }}
                />
                Production environment
              </label>
            </div>
            {createError && <div className="form-error" role="alert">{createError}</div>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
                {saving ? "Creating..." : "Create"}
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowCreate(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {items.length === 0 && !showCreate ? (
        <EmptyState
          title="No environments"
          description="Environments define execution contexts and variables for jobs."
          action={
            hasRole("admin") ? (
              <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
                New Environment
              </button>
            ) : undefined
          }
        />
      ) : items.length > 0 ? (
        <div className="data-table-container">
          <table className="data-table" aria-label="Environments">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Production</th>
                <th>Variables</th>
                <th>Created</th>
                {hasRole("admin") && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {items.map((env) => (
                <tr key={env.id} onClick={() => navigate(`/environments/${env.id}`)} style={{ cursor: "pointer" }}>
                  <td style={{ fontWeight: 500 }}>{env.name}</td>
                  <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {env.description ?? "—"}
                  </td>
                  <td>
                    {env.is_production ? (
                      <span style={{ color: "#dc2626", fontWeight: 600, fontSize: 12 }}>PROD</span>
                    ) : (
                      <span style={{ color: "#6b7280", fontSize: 12 }}>No</span>
                    )}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {env.variables ? Object.keys(env.variables).length + " vars" : "—"}
                  </td>
                  <td>{formatDateTime(env.created_at)}</td>
                  {hasRole("admin") && (
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(env.id);
                        }}
                      >
                        Delete
                      </button>
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
      ) : null}
    </>
  );
}
