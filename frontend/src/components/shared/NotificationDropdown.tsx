import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useEventBus } from "@/services/eventBus";
import { formatRelativeTime } from "@/utils/format";
import type { NotificationSeverity, WsEventType } from "@/types/api";

const SEVERITY_COLORS: Record<NotificationSeverity, string> = {
  info: "#3b82f6",
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
};

const MUTABLE_EVENT_TYPES: { type: WsEventType; label: string }[] = [
  { type: "job.failed", label: "Job Failures" },
  { type: "job.timed_out", label: "Job Timeouts" },
  { type: "job.completed", label: "Job Completions" },
  { type: "job.started", label: "Job Starts" },
  { type: "sla.breached", label: "SLA Breaches" },
  { type: "sla.at_risk", label: "SLA At Risk" },
  { type: "agent.status_changed", label: "Agent Status" },
];

export default function NotificationDropdown() {
  const { notifications, unreadCount, markRead, markAllRead, clearAll, mutedTypes, toggleMute } =
    useEventBus();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
        setShowPrefs(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        setShowPrefs(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  return (
    <div className="notification-dropdown-wrapper" ref={dropdownRef}>
      <button
        className="notification-bell"
        onClick={() => {
          setOpen((prev) => !prev);
          setShowPrefs(false);
        }}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="notification-badge" aria-hidden>
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-dropdown" role="menu">
          <div className="notification-dropdown-header">
            <span className="notification-dropdown-title">Notifications</span>
            <div className="notification-dropdown-actions">
              <button
                className="notification-dropdown-action-btn"
                onClick={() => setShowPrefs((p) => !p)}
                title="Notification preferences"
                aria-label="Notification preferences"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
                </svg>
              </button>
              {notifications.length > 0 && (
                <>
                  <button
                    className="notification-dropdown-action-btn"
                    onClick={markAllRead}
                    title="Mark all as read"
                    aria-label="Mark all as read"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                  </button>
                  <button
                    className="notification-dropdown-action-btn"
                    onClick={clearAll}
                    title="Clear all"
                    aria-label="Clear all notifications"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </>
              )}
            </div>
          </div>

          {showPrefs ? (
            <div className="notification-prefs">
              <div className="notification-prefs-title">Toast Notifications</div>
              <div className="notification-prefs-hint">
                Muted types will still appear in the dropdown but won't show toast popups.
              </div>
              {MUTABLE_EVENT_TYPES.map(({ type, label }) => (
                <label key={type} className="notification-pref-item">
                  <input
                    type="checkbox"
                    checked={!mutedTypes.has(type)}
                    onChange={() => toggleMute(type)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          ) : (
            <div className="notification-list" role="list">
              {notifications.length === 0 ? (
                <div className="notification-empty">No notifications yet</div>
              ) : (
                notifications.slice(0, 30).map((n) => (
                  <button
                    key={n.id}
                    className={`notification-item${n.read ? "" : " notification-item-unread"}`}
                    role="listitem"
                    onClick={() => {
                      markRead(n.id);
                      if (n.linkTo) {
                        navigate(n.linkTo);
                        setOpen(false);
                      }
                    }}
                  >
                    <span
                      className="notification-item-dot"
                      style={{ backgroundColor: SEVERITY_COLORS[n.severity] }}
                      aria-hidden
                    />
                    <div className="notification-item-content">
                      <div className="notification-item-title">{n.title}</div>
                      <div className="notification-item-message">{n.message}</div>
                      <div className="notification-item-time">
                        {formatRelativeTime(n.timestamp)}
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
