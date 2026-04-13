import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { calendars } from "@/services/api";
import type { CalendarType } from "@/types/api";

const CALENDAR_TYPES: CalendarType[] = ["business", "financial", "holiday", "custom"];

export default function CalendarForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const { data: existing } = useApi(
    () => (id ? calendars.get(id) : Promise.resolve(null)),
    [id]
  );

  const [name, setName] = useState("");
  const [calendarType, setCalendarType] = useState<CalendarType>("business");
  const [timezone, setTimezone] = useState("UTC");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (existing) {
      setName(existing.name);
      setCalendarType(existing.calendar_type);
      setTimezone(existing.timezone);
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
        calendar_type: calendarType,
        timezone,
        description: description || null,
      };
      if (isEdit) {
        await calendars.update(id!, payload);
        navigate(`/calendars/${id}`);
      } else {
        const created = await calendars.create(payload);
        navigate(`/calendars/${created.id}`);
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
        <h2>{isEdit ? "Edit Calendar" : "Create Calendar"}</h2>
      </div>

      <div className="card" style={{ maxWidth: 600 }}>
        <form onSubmit={handleSubmit}>
          {error && <div className="form-error" style={{ marginBottom: 16 }}>{error}</div>}

          <div className="form-group">
            <label className="form-label" htmlFor="cal-name">Name</label>
            <input
              id="cal-name"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="cal-type">Type</label>
              <select
                id="cal-type"
                className="form-select"
                value={calendarType}
                onChange={(e) => setCalendarType(e.target.value as CalendarType)}
              >
                {CALENDAR_TYPES.map((t) => (
                  <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="cal-tz">Timezone</label>
              <input
                id="cal-tz"
                className="form-input"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="UTC"
              />
              <span className="form-hint">e.g., America/New_York, Europe/London</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="cal-desc">Description</label>
            <textarea
              id="cal-desc"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn btn-primary" disabled={saving || !name}>
              {saving ? "Saving..." : isEdit ? "Update Calendar" : "Create Calendar"}
            </button>
            <Link to={isEdit ? `/calendars/${id}` : "/calendars"} className="btn btn-secondary">
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
