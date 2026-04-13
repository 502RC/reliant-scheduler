import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { calendars } from "@/services/api";
import { usePermission } from "@/hooks/usePermission";
import type { CalendarDateEntry } from "@/types/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { formatDateTime } from "@/utils/format";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function CalendarDetail() {
  const { id } = useParams<{ id: string }>();
  const canEdit = usePermission("calendar", "write");

  const [viewYear, setViewYear] = useState(new Date().getFullYear());
  const [viewMonth, setViewMonth] = useState(new Date().getMonth());

  const { data: calendar, loading } = useApi(
    () => calendars.get(id!),
    [id]
  );
  const { data: dates } = useApi(
    () => calendars.dates(id!, viewYear, viewMonth + 1),
    [id, viewYear, viewMonth]
  );

  const dateMap = useMemo(() => {
    const map = new Map<string, CalendarDateEntry>();
    if (dates) {
      for (const d of dates) {
        map.set(d.date, d);
      }
    }
    return map;
  }, [dates]);

  const monthDays = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth, 1);
    const lastDay = new Date(viewYear, viewMonth + 1, 0);
    const startPad = firstDay.getDay();
    const days: (number | null)[] = [];

    for (let i = 0; i < startPad; i++) days.push(null);
    for (let d = 1; d <= lastDay.getDate(); d++) days.push(d);

    return days;
  }, [viewYear, viewMonth]);

  const monthLabel = new Date(viewYear, viewMonth).toLocaleString(undefined, {
    month: "long",
    year: "numeric",
  });

  if (loading) return <LoadingSpinner />;
  if (!calendar) return <div className="form-error">Calendar not found</div>;

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to="/calendars" className="btn btn-secondary btn-sm" style={{ marginBottom: 8 }}>
            &larr; Calendars
          </Link>
          <h2>{calendar.name}</h2>
        </div>
        {canEdit && (
          <Link to={`/calendars/${id}/edit`} className="btn btn-primary">
            Edit Calendar
          </Link>
        )}
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="detail-grid">
          <span className="detail-label">Type</span>
          <span className="detail-value">
            <span className="trigger-type-badge">{calendar.calendar_type}</span>
          </span>
          <span className="detail-label">Timezone</span>
          <span className="detail-value">{calendar.timezone}</span>
          <span className="detail-label">Description</span>
          <span className="detail-value">{calendar.description ?? "—"}</span>
          <span className="detail-label">Created</span>
          <span className="detail-value">{formatDateTime(calendar.created_at)}</span>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              if (viewMonth === 0) { setViewMonth(11); setViewYear(viewYear - 1); }
              else setViewMonth(viewMonth - 1);
            }}
            aria-label="Previous month"
          >
            &larr;
          </button>
          <h3 style={{ margin: 0, fontSize: 16 }}>{monthLabel}</h3>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => {
              if (viewMonth === 11) { setViewMonth(0); setViewYear(viewYear + 1); }
              else setViewMonth(viewMonth + 1);
            }}
            aria-label="Next month"
          >
            &rarr;
          </button>
        </div>

        <div className="calendar-grid" role="grid" aria-label={`${monthLabel} calendar`}>
          <div className="calendar-grid-header">
            {WEEKDAYS.map((d) => (
              <div key={d} className="calendar-grid-day-label">{d}</div>
            ))}
          </div>
          <div className="calendar-grid-body">
            {monthDays.map((day, i) => {
              if (day === null) {
                return <div key={`pad-${i}`} className="calendar-cell calendar-cell-empty" />;
              }
              const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const entry = dateMap.get(dateStr);
              const isBusinessDay = entry ? entry.is_business_day : true;
              const isToday =
                day === new Date().getDate() &&
                viewMonth === new Date().getMonth() &&
                viewYear === new Date().getFullYear();

              return (
                <div
                  key={dateStr}
                  className={`calendar-cell${!isBusinessDay ? " calendar-cell-holiday" : ""}${isToday ? " calendar-cell-today" : ""}`}
                  title={entry?.label ?? undefined}
                >
                  <span className="calendar-cell-day">{day}</span>
                  {entry?.label && (
                    <span className="calendar-cell-label">{entry.label}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 12, color: "#6b7280" }}>
          <span><span style={{ display: "inline-block", width: 12, height: 12, background: "#fff", border: "1px solid #e5e7eb", borderRadius: 2, verticalAlign: "middle", marginRight: 4 }} />Business day</span>
          <span><span style={{ display: "inline-block", width: 12, height: 12, background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 2, verticalAlign: "middle", marginRight: 4 }} />Holiday / Non-business</span>
        </div>
      </div>
    </div>
  );
}
