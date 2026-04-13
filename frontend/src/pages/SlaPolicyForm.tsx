import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { slaPolicies } from "@/services/api";

export default function SlaPolicyForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const { data: existing } = useApi(
    () => (id ? slaPolicies.get(id) : Promise.resolve(null)),
    [id]
  );

  const [name, setName] = useState("");
  const [targetTime, setTargetTime] = useState("18:00");
  const [riskMinutes, setRiskMinutes] = useState(30);
  const [breachMinutes, setBreachMinutes] = useState(60);
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setTargetTime(existing.target_completion_time);
      setRiskMinutes(existing.risk_window_minutes);
      setBreachMinutes(existing.breach_window_minutes);
      setDescription(existing.description ?? "");
    }
  }, [existing]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name,
        target_completion_time: targetTime,
        risk_window_minutes: riskMinutes,
        breach_window_minutes: breachMinutes,
        description: description || null,
      };
      if (isEdit) {
        await slaPolicies.update(id!, payload);
        navigate(`/sla-policies/${id}`);
      } else {
        const created = await slaPolicies.create(payload);
        navigate(`/sla-policies/${created.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>{isEdit ? "Edit SLA Policy" : "Create SLA Policy"}</h2>
      </div>

      <div className="card" style={{ maxWidth: 600 }}>
        <form onSubmit={handleSubmit}>
          {error && <div className="form-error" style={{ marginBottom: 16 }}>{error}</div>}

          <div className="form-group">
            <label className="form-label" htmlFor="sla-name">Policy Name</label>
            <input
              id="sla-name"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="sla-target">Target Completion Time</label>
            <input
              id="sla-target"
              className="form-input"
              type="time"
              value={targetTime}
              onChange={(e) => setTargetTime(e.target.value)}
              required
            />
            <span className="form-hint">The time by which all jobs in this SLA must complete</span>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="sla-risk">Risk Window (minutes)</label>
              <input
                id="sla-risk"
                className="form-input"
                type="number"
                min="1"
                value={riskMinutes}
                onChange={(e) => setRiskMinutes(Number(e.target.value))}
                required
              />
              <span className="form-hint">Alert when this close to target</span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="sla-breach">Breach Window (minutes)</label>
              <input
                id="sla-breach"
                className="form-input"
                type="number"
                min="1"
                value={breachMinutes}
                onChange={(e) => setBreachMinutes(Number(e.target.value))}
                required
              />
              <span className="form-hint">SLA breached after target + this</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="sla-desc">Description</label>
            <textarea
              id="sla-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn btn-primary" disabled={saving || !name}>
              {saving ? "Saving..." : isEdit ? "Update Policy" : "Create Policy"}
            </button>
            <Link to={isEdit ? `/sla-policies/${id}` : "/sla-policies"} className="btn btn-secondary">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
