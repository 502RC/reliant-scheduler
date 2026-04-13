import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { schedules } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { TriggerType, ScheduleCreate, ScheduleUpdate } from "@/types/api";

const COMMON_CRON_PRESETS: { label: string; value: string }[] = [
  { label: "Every minute", value: "* * * * *" },
  { label: "Every 5 minutes", value: "*/5 * * * *" },
  { label: "Every hour", value: "0 * * * *" },
  { label: "Daily at midnight", value: "0 0 * * *" },
  { label: "Daily at 6 AM", value: "0 6 * * *" },
  { label: "Weekly (Monday)", value: "0 0 * * 1" },
  { label: "Monthly (1st)", value: "0 0 1 * *" },
];

export default function ScheduleForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [jobId, setJobId] = useState("");
  const [triggerType, setTriggerType] = useState<TriggerType>("cron");
  const [cronExpression, setCronExpression] = useState("0 0 * * *");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [eventSource, setEventSource] = useState("");
  const [eventFilter, setEventFilter] = useState("");
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    schedules.get(id).then((s) => {
      if (cancelled) return;
      setJobId(s.job_id);
      setTriggerType(s.trigger_type);
      setCronExpression(s.cron_expression ?? "");
      setTimezone(s.timezone);
      setEventSource(s.event_source ?? "");
      setEventFilter(s.event_filter ? JSON.stringify(s.event_filter, null, 2) : "");
      setEnabled(s.enabled);
      setLoading(false);
    }).catch(() => {
      if (!cancelled) {
        setError("Failed to load schedule");
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    let parsedFilter: Record<string, unknown> | null = null;
    if (eventFilter.trim()) {
      try {
        parsedFilter = JSON.parse(eventFilter);
      } catch {
        setError("Event filter must be valid JSON");
        setSaving(false);
        return;
      }
    }

    try {
      if (isEdit) {
        const data: ScheduleUpdate = {
          trigger_type: triggerType,
          cron_expression: triggerType === "cron" ? cronExpression : null,
          timezone,
          event_source: triggerType === "event" ? eventSource : null,
          event_filter: triggerType === "event" ? parsedFilter : null,
          enabled,
        };
        await schedules.update(id!, data);
      } else {
        const data: ScheduleCreate = {
          job_id: jobId,
          trigger_type: triggerType,
          cron_expression: triggerType === "cron" ? cronExpression : null,
          timezone,
          event_source: triggerType === "event" ? eventSource : null,
          event_filter: triggerType === "event" ? parsedFilter : null,
          enabled,
        };
        await schedules.create(data);
      }
      navigate("/schedules");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save schedule");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner message="Loading schedule..." />;

  return (
    <>
      <div className="page-header">
        <h2>{isEdit ? "Edit Schedule" : "Create Schedule"}</h2>
      </div>

      <div className="card" style={{ padding: 24, maxWidth: 640 }}>
        <form onSubmit={handleSubmit}>
          {!isEdit && (
            <div className="form-group">
              <label className="form-label" htmlFor="jobId">Job ID *</label>
              <input
                id="jobId"
                className="form-input"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                required
                placeholder="UUID of the job to schedule"
              />
            </div>
          )}

          <div className="form-group">
            <label className="form-label" htmlFor="triggerType">Trigger Type *</label>
            <select
              id="triggerType"
              className="form-select"
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as TriggerType)}
            >
              <option value="cron">Cron</option>
              <option value="event">Event</option>
            </select>
          </div>

          {triggerType === "cron" && (
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="cronExpression">Cron Expression *</label>
                <input
                  id="cronExpression"
                  className="form-input"
                  style={{ fontFamily: "monospace" }}
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  required
                  placeholder="* * * * *"
                />
                <div className="form-hint">
                  Presets:{" "}
                  {COMMON_CRON_PRESETS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      style={{ margin: "2px 2px", fontSize: 11 }}
                      onClick={() => setCronExpression(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="timezone">Timezone</label>
                <input
                  id="timezone"
                  className="form-input"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="UTC"
                />
              </div>
            </>
          )}

          {triggerType === "event" && (
            <>
              <div className="form-group">
                <label className="form-label" htmlFor="eventSource">Event Source *</label>
                <input
                  id="eventSource"
                  className="form-input"
                  value={eventSource}
                  onChange={(e) => setEventSource(e.target.value)}
                  required
                  placeholder="e.g. azure_servicebus, file_watcher"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="eventFilter">Event Filter (JSON)</label>
                <textarea
                  id="eventFilter"
                  className="form-textarea"
                  style={{ fontFamily: "monospace" }}
                  value={eventFilter}
                  onChange={(e) => setEventFilter(e.target.value)}
                  placeholder='{"topic": "orders", "subscription": "process-new"}'
                />
              </div>
            </>
          )}

          <div className="form-group">
            <label className="form-label">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                style={{ marginRight: 8 }}
              />
              Enabled
            </label>
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving..." : isEdit ? "Update Schedule" : "Create Schedule"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/schedules")}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
