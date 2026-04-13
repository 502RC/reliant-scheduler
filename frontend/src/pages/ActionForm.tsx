import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { actions } from "@/services/api";
import { useApi } from "@/hooks/useApi";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { ActionType, ActionTestResult } from "@/types/api";

const ACTION_TYPES: { value: ActionType; label: string; description: string }[] = [
  { value: "email", label: "Email", description: "Send email notifications with customizable templates" },
  { value: "webhook", label: "Webhook", description: "POST to an external HTTP endpoint" },
  { value: "slack", label: "Slack", description: "Send messages to a Slack channel via webhook" },
  { value: "teams", label: "Microsoft Teams", description: "Send messages to a Teams channel via webhook" },
  { value: "itsm", label: "ITSM", description: "Create incidents in ServiceNow or similar ITSM" },
];

interface FormState {
  name: string;
  action_type: ActionType;
  definition: Record<string, string>;
}

const DEFAULT_DEFINITIONS: Record<ActionType, Record<string, string>> = {
  email: { to: "", subject: "", body_template: "" },
  webhook: { url: "", method: "POST", headers: "{}", body_template: "" },
  slack: { webhook_url: "", channel: "", message_template: "" },
  teams: { webhook_url: "", message_template: "" },
  itsm: { endpoint: "", auth_type: "basic", username: "", payload_template: "" },
};

export default function ActionForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const existing = useApi(() => (id ? actions.get(id) : Promise.resolve(null)), [id]);

  const [form, setForm] = useState<FormState>({
    name: "",
    action_type: "email",
    definition: { ...DEFAULT_DEFINITIONS.email },
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ActionTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setForm({
        name: existing.data.name,
        action_type: existing.data.action_type,
        definition: existing.data.definition as Record<string, string>,
      });
    }
  }, [existing.data]);

  if (isEdit && existing.loading) return <LoadingSpinner message="Loading action..." />;

  const handleTypeChange = (type: ActionType) => {
    setForm((prev) => ({
      ...prev,
      action_type: type,
      definition: { ...DEFAULT_DEFINITIONS[type] },
    }));
    setTestResult(null);
  };

  const handleDefField = (key: string, value: string) => {
    setForm((prev) => ({
      ...prev,
      definition: { ...prev.definition, [key]: value },
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (isEdit) {
        await actions.update(id!, {
          name: form.name,
          action_type: form.action_type,
          definition: form.definition,
        });
      } else {
        await actions.create({
          name: form.name,
          action_type: form.action_type,
          definition: form.definition,
        });
      }
      navigate("/actions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save action");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!id) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await actions.test(id);
      setTestResult(result);
    } catch (err) {
      setTestResult({
        success: false,
        message: err instanceof Error ? err.message : "Test failed",
        response_time_ms: 0,
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>{isEdit ? "Edit Action" : "Create Action"}</h2>
      </div>

      <form onSubmit={handleSubmit} className="card" style={{ padding: 24, maxWidth: 720 }}>
        {error && (
          <div className="form-error" style={{ marginBottom: 16, padding: 10, background: "#fef2f2", borderRadius: 6 }}>
            {error}
          </div>
        )}

        <div className="form-group">
          <label className="form-label" htmlFor="action-name">Name</label>
          <input
            id="action-name"
            className="form-input"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
            placeholder="e.g., Ops Team Slack Alert"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Action Type</label>
          <div className="action-type-grid">
            {ACTION_TYPES.map((t) => (
              <button
                key={t.value}
                type="button"
                className={`action-type-card${form.action_type === t.value ? " action-type-card-selected" : ""}`}
                onClick={() => handleTypeChange(t.value)}
              >
                <strong>{t.label}</strong>
                <span>{t.description}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Configuration</label>
          {renderDefinitionFields(form.action_type, form.definition, handleDefField)}
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving..." : isEdit ? "Update Action" : "Create Action"}
          </button>
          {isEdit && (
            <button type="button" className="btn btn-secondary" onClick={handleTest} disabled={testing}>
              {testing ? "Testing..." : "Send Test"}
            </button>
          )}
          <button type="button" className="btn btn-secondary" onClick={() => navigate("/actions")}>
            Cancel
          </button>
        </div>

        {testResult && (
          <div
            className="card"
            style={{
              marginTop: 16,
              padding: 12,
              background: testResult.success ? "#f0fdf4" : "#fef2f2",
              border: `1px solid ${testResult.success ? "#bbf7d0" : "#fecdd3"}`,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13, color: testResult.success ? "#15803d" : "#be123c" }}>
              {testResult.success ? "Test Successful" : "Test Failed"}
            </div>
            <div style={{ fontSize: 12, color: "#374151", marginTop: 4 }}>{testResult.message}</div>
            {testResult.response_time_ms > 0 && (
              <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 2 }}>
                Response time: {testResult.response_time_ms}ms
              </div>
            )}
          </div>
        )}
      </form>
    </>
  );
}

function renderDefinitionFields(
  type: ActionType,
  def: Record<string, string>,
  onChange: (key: string, value: string) => void
) {
  switch (type) {
    case "email":
      return (
        <div className="action-config-fields">
          <div className="form-group">
            <label className="form-label" htmlFor="def-to">To Addresses</label>
            <input
              id="def-to"
              className="form-input"
              value={def.to ?? ""}
              onChange={(e) => onChange("to", e.target.value)}
              placeholder="user@example.com, team@example.com"
            />
            <div className="form-hint">Comma-separated email addresses</div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-subject">Subject Template</label>
            <input
              id="def-subject"
              className="form-input"
              value={def.subject ?? ""}
              onChange={(e) => onChange("subject", e.target.value)}
              placeholder="[Alert] {{job_name}} {{status}}"
            />
            <div className="form-hint">Use {"{{variable}}"} for template variables</div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-body">Body Template</label>
            <textarea
              id="def-body"
              className="form-textarea"
              value={def.body_template ?? ""}
              onChange={(e) => onChange("body_template", e.target.value)}
              placeholder={"Job {{job_name}} changed to {{status}} at {{timestamp}}"}
              rows={4}
            />
          </div>
        </div>
      );

    case "webhook":
      return (
        <div className="action-config-fields">
          <div className="form-group">
            <label className="form-label" htmlFor="def-url">Webhook URL</label>
            <input
              id="def-url"
              className="form-input"
              value={def.url ?? ""}
              onChange={(e) => onChange("url", e.target.value)}
              placeholder="https://api.example.com/webhook"
              type="url"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-headers">Headers (JSON)</label>
            <textarea
              id="def-headers"
              className="form-textarea"
              value={def.headers ?? "{}"}
              onChange={(e) => onChange("headers", e.target.value)}
              placeholder='{"Content-Type": "application/json"}'
              rows={3}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-body-tpl">Body Template</label>
            <textarea
              id="def-body-tpl"
              className="form-textarea"
              value={def.body_template ?? ""}
              onChange={(e) => onChange("body_template", e.target.value)}
              placeholder={'{"text": "{{job_name}} {{status}}"}'}
              rows={4}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-hmac">HMAC Secret (optional)</label>
            <input
              id="def-hmac"
              className="form-input"
              value={def.hmac_secret ?? ""}
              onChange={(e) => onChange("hmac_secret", e.target.value)}
              placeholder="Optional HMAC signing secret"
              type="password"
            />
          </div>
        </div>
      );

    case "slack":
      return (
        <div className="action-config-fields">
          <div className="form-group">
            <label className="form-label" htmlFor="def-slack-url">Slack Webhook URL</label>
            <input
              id="def-slack-url"
              className="form-input"
              value={def.webhook_url ?? ""}
              onChange={(e) => onChange("webhook_url", e.target.value)}
              placeholder="https://hooks.slack.com/services/..."
              type="url"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-slack-channel">Channel</label>
            <input
              id="def-slack-channel"
              className="form-input"
              value={def.channel ?? ""}
              onChange={(e) => onChange("channel", e.target.value)}
              placeholder="#ops-alerts"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-slack-tpl">Message Template</label>
            <textarea
              id="def-slack-tpl"
              className="form-textarea"
              value={def.message_template ?? ""}
              onChange={(e) => onChange("message_template", e.target.value)}
              placeholder={":warning: Job *{{job_name}}* is {{status}}"}
              rows={4}
            />
          </div>
        </div>
      );

    case "teams":
      return (
        <div className="action-config-fields">
          <div className="form-group">
            <label className="form-label" htmlFor="def-teams-url">Teams Webhook URL</label>
            <input
              id="def-teams-url"
              className="form-input"
              value={def.webhook_url ?? ""}
              onChange={(e) => onChange("webhook_url", e.target.value)}
              placeholder="https://outlook.office.com/webhook/..."
              type="url"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-teams-tpl">Message Template</label>
            <textarea
              id="def-teams-tpl"
              className="form-textarea"
              value={def.message_template ?? ""}
              onChange={(e) => onChange("message_template", e.target.value)}
              placeholder={"Job {{job_name}} status: {{status}}"}
              rows={4}
            />
          </div>
        </div>
      );

    case "itsm":
      return (
        <div className="action-config-fields">
          <div className="form-group">
            <label className="form-label" htmlFor="def-itsm-endpoint">ITSM Endpoint</label>
            <input
              id="def-itsm-endpoint"
              className="form-input"
              value={def.endpoint ?? ""}
              onChange={(e) => onChange("endpoint", e.target.value)}
              placeholder="https://instance.service-now.com/api/now/table/incident"
              type="url"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-itsm-auth">Auth Type</label>
            <select
              id="def-itsm-auth"
              className="form-select"
              value={def.auth_type ?? "basic"}
              onChange={(e) => onChange("auth_type", e.target.value)}
            >
              <option value="basic">Basic Auth</option>
              <option value="oauth2">OAuth2</option>
              <option value="api_key">API Key</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="def-itsm-payload">Payload Template</label>
            <textarea
              id="def-itsm-payload"
              className="form-textarea"
              value={def.payload_template ?? ""}
              onChange={(e) => onChange("payload_template", e.target.value)}
              placeholder={'{"short_description": "Job {{job_name}} failed", "urgency": "2"}'}
              rows={4}
            />
          </div>
        </div>
      );
  }
}
