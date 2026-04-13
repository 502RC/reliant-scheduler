import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { calendars } from "@/services/api";
import { usePermission } from "@/hooks/usePermission";
import type { CalendarResponse, CalendarType } from "@/types/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";

const CALENDAR_TYPES: CalendarType[] = ["business", "financial", "holiday", "custom"];

function typeLabel(t: string): string {
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export default function CalendarsList() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState<string>("");
  const canCreate = usePermission("calendar", "write");

  const { data, loading, error } = useApi(
    () => calendars.list(page, 20, typeFilter || undefined),
    [page, typeFilter]
  );

  return (
    <div>
      <div className="page-header">
        <h2>Calendars</h2>
        {canCreate && (
          <Link to="/calendars/new" className="btn btn-primary">
            Create Calendar
          </Link>
        )}
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          aria-label="Filter by calendar type"
        >
          <option value="">All types</option>
          {CALENDAR_TYPES.map((t) => (
            <option key={t} value={t}>{typeLabel(t)}</option>
          ))}
        </select>
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load calendars: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No calendars"
          description="Create a calendar to define business days, holidays, and scheduling rules."
        />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Timezone</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((cal: CalendarResponse) => (
                <tr key={cal.id}>
                  <td>
                    <Link to={`/calendars/${cal.id}`}>{cal.name}</Link>
                  </td>
                  <td>
                    <span className="trigger-type-badge">{typeLabel(cal.calendar_type)}</span>
                  </td>
                  <td>{cal.timezone}</td>
                  <td>{cal.description ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} calendar{data.total !== 1 ? "s" : ""}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page} of {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
