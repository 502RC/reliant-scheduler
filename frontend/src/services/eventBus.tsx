import { createContext, useContext, useCallback, useEffect, useState, useRef } from "react";
import type { ReactNode } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  WsEvent,
  WsConnectionStatus,
  AppNotification,
  NotificationSeverity,
  WsJobStatusPayload,
  WsAgentStatusPayload,
  WsSlaPayload,
  WsEventType,
} from "@/types/api";

const MAX_NOTIFICATIONS = 50;
const MUTED_TYPES_KEY = "reliant:muted-notification-types";

function loadMutedTypes(): Set<WsEventType> {
  try {
    const raw = localStorage.getItem(MUTED_TYPES_KEY);
    if (raw) return new Set(JSON.parse(raw) as WsEventType[]);
  } catch { /* ignore */ }
  return new Set();
}

function saveMutedTypes(types: Set<WsEventType>) {
  localStorage.setItem(MUTED_TYPES_KEY, JSON.stringify([...types]));
}

interface EventBusContextValue {
  /** WebSocket connection status */
  connectionStatus: WsConnectionStatus;
  /** Subscribe to a specific event type (or all with "*") */
  subscribe: (handler: (event: WsEvent) => void) => () => void;
  /** All notifications (most recent first) */
  notifications: AppNotification[];
  /** Count of unread notifications */
  unreadCount: number;
  /** Mark a notification as read */
  markRead: (id: string) => void;
  /** Mark all notifications as read */
  markAllRead: () => void;
  /** Clear all notifications */
  clearAll: () => void;
  /** Muted event types */
  mutedTypes: Set<WsEventType>;
  /** Toggle mute for an event type */
  toggleMute: (type: WsEventType) => void;
  /** Active toasts to display */
  toasts: AppNotification[];
  /** Dismiss a toast */
  dismissToast: (id: string) => void;
}

const EventBusContext = createContext<EventBusContextValue | null>(null);

function eventToNotification(event: WsEvent): AppNotification {
  const id = `${event.type}-${event.timestamp}-${Math.random().toString(36).slice(2, 8)}`;
  let title = "";
  let message = "";
  let severity: NotificationSeverity = "info";
  let linkTo: string | undefined;

  switch (event.type) {
    case "job.status_changed":
    case "job.started": {
      const p = event.payload as WsJobStatusPayload;
      title = `Job ${event.type === "job.started" ? "Started" : "Status Changed"}`;
      message = `${p.job_name}: ${p.previous_status ?? "new"} \u2192 ${p.status}`;
      severity = "info";
      linkTo = `/jobs/${p.job_id}/runs/${p.run_id}`;
      break;
    }
    case "job.completed": {
      const p = event.payload as WsJobStatusPayload;
      title = "Job Completed";
      message = `${p.job_name} completed successfully`;
      severity = "success";
      linkTo = `/jobs/${p.job_id}/runs/${p.run_id}`;
      break;
    }
    case "job.failed": {
      const p = event.payload as WsJobStatusPayload;
      title = "Job Failed";
      message = p.error_message ? `${p.job_name}: ${p.error_message}` : `${p.job_name} failed`;
      severity = "error";
      linkTo = `/jobs/${p.job_id}/runs/${p.run_id}`;
      break;
    }
    case "job.timed_out": {
      const p = event.payload as WsJobStatusPayload;
      title = "Job Timed Out";
      message = `${p.job_name} exceeded timeout`;
      severity = "warning";
      linkTo = `/jobs/${p.job_id}/runs/${p.run_id}`;
      break;
    }
    case "agent.status_changed": {
      const p = event.payload as WsAgentStatusPayload;
      title = "Agent Status Changed";
      message = `${p.hostname}: ${p.previous_status} \u2192 ${p.status}`;
      severity = p.status === "offline" ? "warning" : "info";
      linkTo = "/agents";
      break;
    }
    case "sla.at_risk": {
      const p = event.payload as WsSlaPayload;
      title = "SLA At Risk";
      message = p.message ?? `${p.sla_policy_name} is at risk`;
      severity = "warning";
      linkTo = `/sla-policies/${p.sla_policy_id}`;
      break;
    }
    case "sla.breached": {
      const p = event.payload as WsSlaPayload;
      title = "SLA Breached";
      message = p.message ?? `${p.sla_policy_name} has been breached`;
      severity = "error";
      linkTo = `/sla-policies/${p.sla_policy_id}`;
      break;
    }
    case "sla.met": {
      const p = event.payload as WsSlaPayload;
      title = "SLA Met";
      message = p.message ?? `${p.sla_policy_name} target met`;
      severity = "success";
      linkTo = `/sla-policies/${p.sla_policy_id}`;
      break;
    }
    default: {
      title = "System Event";
      message = String((event.payload as unknown as Record<string, unknown>).message ?? "");
      severity = "info";
    }
  }

  return {
    id,
    type: event.type,
    title,
    message,
    severity,
    timestamp: event.timestamp,
    read: false,
    linkTo,
  };
}

const CRITICAL_TYPES: Set<WsEventType> = new Set([
  "job.failed",
  "job.timed_out",
  "sla.breached",
  "sla.at_risk",
]);

const TOAST_AUTO_CLOSE_MS = 5000;

export function EventBusProvider({ children }: { children: ReactNode }) {
  const { status, subscribe: wsSubscribe } = useWebSocket();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const [mutedTypes, setMutedTypes] = useState<Set<WsEventType>>(loadMutedTypes);
  const mutedTypesRef = useRef(mutedTypes);
  mutedTypesRef.current = mutedTypes;

  // Auto-dismiss toasts
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts((prev) => prev.slice(1));
    }, TOAST_AUTO_CLOSE_MS);
    return () => clearTimeout(timer);
  }, [toasts]);

  // Process incoming WebSocket events
  useEffect(() => {
    const unsubscribe = wsSubscribe((event: WsEvent) => {
      const notification = eventToNotification(event);

      setNotifications((prev) => {
        const next = [notification, ...prev];
        return next.length > MAX_NOTIFICATIONS ? next.slice(0, MAX_NOTIFICATIONS) : next;
      });

      // Show toast for critical events if not muted
      if (CRITICAL_TYPES.has(event.type) && !mutedTypesRef.current.has(event.type)) {
        setToasts((prev) => [...prev, notification]);
      }
    });
    return unsubscribe;
  }, [wsSubscribe]);

  const markRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const toggleMute = useCallback((type: WsEventType) => {
    setMutedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      saveMutedTypes(next);
      return next;
    });
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <EventBusContext.Provider
      value={{
        connectionStatus: status,
        subscribe: wsSubscribe,
        notifications,
        unreadCount,
        markRead,
        markAllRead,
        clearAll,
        mutedTypes,
        toggleMute,
        toasts,
        dismissToast,
      }}
    >
      {children}
    </EventBusContext.Provider>
  );
}

export function useEventBus(): EventBusContextValue {
  const ctx = useContext(EventBusContext);
  if (!ctx) {
    throw new Error("useEventBus must be used within an EventBusProvider");
  }
  return ctx;
}
