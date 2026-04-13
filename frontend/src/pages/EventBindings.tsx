import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { events, actions as actionsApi, eventActions } from "@/services/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatRelativeTime } from "@/utils/format";
import type { EventDefinitionType, ActionType } from "@/types/api";

const EVENT_TYPE_LABELS: Record<EventDefinitionType, string> = {
  file_arrival: "File Arrival",
  database_change: "Database Change",
  sla_event: "SLA Event",
  system_event: "System Event",
  job_event: "Job Event",
};

const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  email: "Email",
  webhook: "Webhook",
  slack: "Slack",
  teams: "Teams",
  itsm: "ITSM",
};

export default function EventBindings() {
  const eventsResult = useApi(() => events.list(1, 100), []);
  const actionsResult = useApi(() => actionsApi.list(1, 100), []);
  const bindingsResult = useApi(() => eventActions.list(), []);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newBinding, setNewBinding] = useState({ event_id: "", action_id: "", order: 1 });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (eventsResult.loading || actionsResult.loading || bindingsResult.loading) {
    return <LoadingSpinner message="Loading event bindings..." />;
  }

  const allEvents = eventsResult.data?.items ?? [];
  const allActions = actionsResult.data?.items ?? [];
  const bindings = bindingsResult.data?.items ?? [];

  const eventsById = Object.fromEntries(allEvents.map((e) => [e.id, e]));
  const actionsById = Object.fromEntries(allActions.map((a) => [a.id, a]));

  const handleCreate = async () => {
    if (!newBinding.event_id || !newBinding.action_id) return;
    setSaving(true);
    setError(null);
    try {
      await eventActions.create({
        event_id: newBinding.event_id,
        action_id: newBinding.action_id,
        order: newBinding.order,
        active: true,
      });
      setShowCreateModal(false);
      setNewBinding({ event_id: "", action_id: "", order: 1 });
      bindingsResult.refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create binding");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (bindingId: string) => {
    try {
      await eventActions.delete(bindingId);
      bindingsResult.refetch();
    } catch {
      // Silently fail for now
    }
  };

  const handleToggle = async (bindingId: string, currentActive: boolean) => {
    try {
      await eventActions.update(bindingId, { active: !currentActive });
      bindingsResult.refetch();
    } catch {
      // Silently fail
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>Event Bindings</h2>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          Add Binding
        </button>
      </div>

      {bindings.length === 0 ? (
        <EmptyState
          title="No event bindings"
          description="Connect events to actions to automate notifications and responses when specific conditions occur."
          actionLabel="Add Binding"
          actionOnClick={() => setShowCreateModal(true)}
        />
      ) : (
        <div className="data-table-container">
          <table className="data-table" aria-label="Event-action bindings">
            <thead>
              <tr>
                <th>Event</th>
                <th>Action</th>
                <th>Order</th>
                <th>Active</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((binding) => {
                const evt = eventsById[binding.event_id];
                const act = actionsById[binding.action_id];
                return (
                  <tr key={binding.id}>
                    <td>
                      <div>
                        <div style={{ fontWeight: 500 }}>{evt?.name ?? "Unknown"}</div>
                        {evt && (
                          <div style={{ fontSize: 11, color: "#6b7280" }}>
                            {EVENT_TYPE_LABELS[evt.event_type] ?? evt.event_type}
                          </div>
                        )}
                      </div>
                    </td>
                    <td>
                      <div>
                        <div style={{ fontWeight: 500 }}>{act?.name ?? "Unknown"}</div>
                        {act && (
                          <div style={{ fontSize: 11, color: "#6b7280" }}>
                            {ACTION_TYPE_LABELS[act.action_type] ?? act.action_type}
                          </div>
                        )}
                      </div>
                    </td>
                    <td>{binding.order}</td>
                    <td>
                      <button
                        className={`toggle-btn ${binding.active ? "toggle-on" : "toggle-off"}`}
                        onClick={() => handleToggle(binding.id, binding.active)}
                        aria-label={binding.active ? "Deactivate binding" : "Activate binding"}
                      >
                        <span className="toggle-knob" />
                      </button>
                    </td>
                    <td>{formatRelativeTime(binding.updated_at)}</td>
                    <td>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(binding.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 16 }}>Add Event Binding</h3>

            {error && (
              <div className="form-error" style={{ marginBottom: 12, padding: 8, background: "#fef2f2", borderRadius: 6 }}>
                {error}
              </div>
            )}

            <div className="form-group">
              <label className="form-label" htmlFor="binding-event">Event</label>
              <select
                id="binding-event"
                className="form-select"
                value={newBinding.event_id}
                onChange={(e) => setNewBinding((prev) => ({ ...prev, event_id: e.target.value }))}
              >
                <option value="">Select an event...</option>
                {allEvents.filter((ev) => ev.enabled).map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.name} ({EVENT_TYPE_LABELS[ev.event_type] ?? ev.event_type})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="binding-action">Action</label>
              <select
                id="binding-action"
                className="form-select"
                value={newBinding.action_id}
                onChange={(e) => setNewBinding((prev) => ({ ...prev, action_id: e.target.value }))}
              >
                <option value="">Select an action...</option>
                {allActions.map((act) => (
                  <option key={act.id} value={act.id}>
                    {act.name} ({ACTION_TYPE_LABELS[act.action_type] ?? act.action_type})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="binding-order">Execution Order</label>
              <input
                id="binding-order"
                className="form-input"
                type="number"
                min={1}
                value={newBinding.order}
                onChange={(e) => setNewBinding((prev) => ({ ...prev, order: parseInt(e.target.value) || 1 }))}
              />
              <div className="form-hint">Lower numbers execute first when multiple actions are bound to the same event</div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button className="btn btn-primary" onClick={handleCreate} disabled={saving || !newBinding.event_id || !newBinding.action_id}>
                {saving ? "Creating..." : "Create Binding"}
              </button>
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
