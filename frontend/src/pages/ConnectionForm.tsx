import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { connections } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { ConnectionType, ConnectionCreate, ConnectionUpdate } from "@/types/api";

const CONNECTION_TYPES: { value: ConnectionType; label: string; category: string }[] = [
  { value: "database", label: "Database (JDBC)", category: "Generic" },
  { value: "rest_api", label: "REST / WebService", category: "Generic" },
  { value: "sftp", label: "SSH / SFTP", category: "Generic" },
  { value: "azure_blob", label: "Azure Blob Storage", category: "Azure" },
  { value: "azure_servicebus", label: "Azure Service Bus", category: "Azure" },
  { value: "azure_eventhub", label: "Azure Event Hubs", category: "Azure" },
  { value: "custom", label: "Custom", category: "Other" },
];

export default function ConnectionForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [connectionType, setConnectionType] = useState<ConnectionType>("database");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("");
  const [description, setDescription] = useState("");
  const [extra, setExtra] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    connections.get(id).then((c) => {
      if (cancelled) return;
      setName(c.name);
      setConnectionType(c.connection_type as ConnectionType);
      setHost(c.host ?? "");
      setPort(c.port != null ? String(c.port) : "");
      setDescription(c.description ?? "");
      setExtra(c.extra ? JSON.stringify(c.extra, null, 2) : "");
      setLoading(false);
    }).catch(() => {
      if (!cancelled) {
        setError("Failed to load connection");
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    let parsedExtra: Record<string, unknown> | null = null;
    if (extra.trim()) {
      try {
        parsedExtra = JSON.parse(extra);
      } catch {
        setError("Extra config must be valid JSON");
        setSaving(false);
        return;
      }
    }

    const portNum = port ? parseInt(port, 10) : null;

    try {
      if (isEdit) {
        const data: ConnectionUpdate = {
          name,
          connection_type: connectionType,
          host: host || null,
          port: portNum,
          description: description || null,
          extra: parsedExtra,
        };
        await connections.update(id!, data);
      } else {
        const data: ConnectionCreate = {
          name,
          connection_type: connectionType,
          host: host || null,
          port: portNum,
          description: description || null,
          extra: parsedExtra,
        };
        await connections.create(data);
      }
      navigate("/connections");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save connection");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner message="Loading connection..." />;

  return (
    <>
      <div className="page-header">
        <h2>{isEdit ? "Edit Connection" : "New Connection"}</h2>
      </div>

      <div className="card" style={{ padding: 24, maxWidth: 640 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Name *</label>
            <input
              id="name"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. prod-postgres, azure-blob-logs"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="connectionType">Connection Type *</label>
            <select
              id="connectionType"
              className="form-select"
              value={connectionType}
              onChange={(e) => setConnectionType(e.target.value as ConnectionType)}
            >
              {CONNECTION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.category}: {t.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="host">Host</label>
              <input
                id="host"
                className="form-input"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="hostname or IP"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="port">Port</label>
              <input
                id="port"
                className="form-input"
                type="number"
                value={port}
                onChange={(e) => setPort(e.target.value)}
                placeholder="e.g. 5432"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="description">Description</label>
            <textarea
              id="description"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="extra">Extra Configuration (JSON)</label>
            <textarea
              id="extra"
              className="form-textarea"
              style={{ fontFamily: "monospace" }}
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              placeholder='{"connection_string": "...", "ssl": true}'
            />
            <div className="form-hint">
              Connection-specific settings as JSON (e.g., connection string, SSL config, SAS tokens)
            </div>
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : isEdit ? "Update Connection" : "Create Connection"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/connections")}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
