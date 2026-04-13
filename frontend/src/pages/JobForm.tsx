import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { jobs, connections } from "@/services/api";
import { useApi } from "@/hooks/useApi";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { JobCreate } from "@/types/api";

const JOB_TYPES = ["shell", "ssh", "python", "sql", "database", "http", "file_transfer", "databricks", "custom"];

export default function JobForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [jobType, setJobType] = useState("shell");
  const [command, setCommand] = useState("");
  const [maxRetries, setMaxRetries] = useState(0);
  const [timeoutSeconds, setTimeoutSeconds] = useState(3600);
  const [environmentId, setEnvironmentId] = useState("");
  const [parametersJson, setParametersJson] = useState("");
  const [tagsJson, setTagsJson] = useState("");
  const [connectionId, setConnectionId] = useState("");

  const connectionsResult = useApi(() => connections.list(), []);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    jobs.get(id).then((job) => {
      if (cancelled) return;
      setName(job.name);
      setDescription(job.description ?? "");
      setJobType(job.job_type);
      setCommand(job.command ?? "");
      setMaxRetries(job.max_retries);
      setTimeoutSeconds(job.timeout_seconds);
      setEnvironmentId(job.environment_id ?? "");
      setParametersJson(
        job.parameters ? JSON.stringify(job.parameters, null, 2) : ""
      );
      setTagsJson(job.tags ? JSON.stringify(job.tags, null, 2) : "");
      setConnectionId(job.connection_id ?? "");
      setLoading(false);
    }).catch((err) => {
      if (!cancelled) {
        setError(err instanceof Error ? err.message : "Failed to load job");
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [id]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    let parameters: Record<string, unknown> | null = null;
    let tags: Record<string, string> | null = null;

    if (parametersJson.trim()) {
      try {
        parameters = JSON.parse(parametersJson);
      } catch {
        setError("Parameters must be valid JSON");
        setSaving(false);
        return;
      }
    }

    if (tagsJson.trim()) {
      try {
        tags = JSON.parse(tagsJson);
      } catch {
        setError("Tags must be valid JSON");
        setSaving(false);
        return;
      }
    }

    const payload: JobCreate = {
      name,
      description: description || null,
      job_type: jobType,
      command: command || null,
      parameters,
      environment_id: environmentId || null,
      connection_id: connectionId || null,
      max_retries: maxRetries,
      timeout_seconds: timeoutSeconds,
      tags,
    };

    try {
      if (isEdit && id) {
        await jobs.update(id, payload);
        navigate(`/jobs/${id}`);
      } else {
        const created = await jobs.create(payload);
        navigate(`/jobs/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save job");
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner message="Loading job..." />;

  return (
    <>
      <div className="page-header">
        <h2>{isEdit ? "Edit Job" : "Create Job"}</h2>
      </div>

      <div className="card" style={{ padding: 24, maxWidth: 720 }}>
        {error && (
          <div role="alert" className="form-error" style={{ marginBottom: 16, padding: 12, background: "#fef2f2", borderRadius: 6 }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="job-name">
              Name *
            </label>
            <input
              id="job-name"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Daily_GL_Close"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="job-description">
              Description
            </label>
            <textarea
              id="job-description"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this job do?"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="job-type">
                Job Type *
              </label>
              <select
                id="job-type"
                className="form-select"
                value={jobType}
                onChange={(e) => setJobType(e.target.value)}
              >
                {JOB_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            {["ssh", "database", "file_transfer"].includes(jobType) && (
              <div className="form-group">
                <label className="form-label" htmlFor="job-connection">
                  Connection *
                </label>
                <select
                  id="job-connection"
                  className="form-select"
                  value={connectionId}
                  onChange={(e) => setConnectionId(e.target.value)}
                >
                  <option value="">Select a connection...</option>
                  {(connectionsResult.data as any)?.items?.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.connection_type})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="job-env">
                Environment ID
              </label>
              <input
                id="job-env"
                className="form-input"
                value={environmentId}
                onChange={(e) => setEnvironmentId(e.target.value)}
                placeholder="UUID (optional)"
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="job-command">
              Command
            </label>
            <textarea
              id="job-command"
              className="form-textarea"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder={["ssh"].includes(jobType) ? "Command to run on remote host (e.g. Get-ChildItem C:\)" : "Shell command or script path"}
              style={{ fontFamily: "monospace" }}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="job-retries">
                Max Retries
              </label>
              <input
                id="job-retries"
                className="form-input"
                type="number"
                min={0}
                value={maxRetries}
                onChange={(e) => setMaxRetries(Number(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="job-timeout">
                Timeout (seconds)
              </label>
              <input
                id="job-timeout"
                className="form-input"
                type="number"
                min={1}
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="job-params">
              Parameters (JSON)
            </label>
            <textarea
              id="job-params"
              className="form-textarea"
              value={parametersJson}
              onChange={(e) => setParametersJson(e.target.value)}
              placeholder='{"key": "value"}'
              style={{ fontFamily: "monospace" }}
            />
            <div className="form-hint">Key-value pairs in JSON format</div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="job-tags">
              Tags (JSON)
            </label>
            <textarea
              id="job-tags"
              className="form-textarea"
              value={tagsJson}
              onChange={(e) => setTagsJson(e.target.value)}
              placeholder='{"team": "finance"}'
              style={{ fontFamily: "monospace" }}
            />
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
            <button type="submit" className="btn btn-primary" disabled={saving || !name}>
              {saving ? "Saving..." : isEdit ? "Update Job" : "Create Job"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(isEdit && id ? `/jobs/${id}` : "/jobs")}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
