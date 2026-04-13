import { useNavigate } from "react-router-dom";
import { useEventBus } from "@/services/eventBus";
import type { NotificationSeverity } from "@/types/api";

const SEVERITY_ICON_COLORS: Record<NotificationSeverity, string> = {
  info: "#3b82f6",
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
};

export default function ToastContainer() {
  const { toasts, dismissToast } = useEventBus();
  const navigate = useNavigate();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-live="polite" aria-label="Notifications">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="toast"
          role="alert"
        >
          <span
            className="toast-severity-bar"
            style={{ backgroundColor: SEVERITY_ICON_COLORS[toast.severity] }}
            aria-hidden
          />
          <div className="toast-body">
            <div className="toast-title">{toast.title}</div>
            <div className="toast-message">{toast.message}</div>
            {toast.linkTo && (
              <button
                className="toast-link"
                onClick={() => {
                  navigate(toast.linkTo!);
                  dismissToast(toast.id);
                }}
              >
                View details
              </button>
            )}
          </div>
          <button
            className="toast-close"
            onClick={() => dismissToast(toast.id)}
            aria-label="Dismiss notification"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
