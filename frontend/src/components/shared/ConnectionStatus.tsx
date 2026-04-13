import type { WsConnectionStatus } from "@/types/api";

const STATUS_CONFIG: Record<WsConnectionStatus, { label: string; color: string; pulse: boolean }> = {
  connected: { label: "Live", color: "#10b981", pulse: false },
  connecting: { label: "Connecting", color: "#f59e0b", pulse: true },
  reconnecting: { label: "Reconnecting", color: "#f59e0b", pulse: true },
  disconnected: { label: "Offline", color: "#9ca3af", pulse: false },
};

export default function ConnectionStatus({ status }: { status: WsConnectionStatus }) {
  const config = STATUS_CONFIG[status];

  return (
    <div
      className="connection-status"
      role="status"
      aria-label={`Connection status: ${config.label}`}
      title={`Real-time updates: ${config.label}`}
    >
      <span
        className={`connection-dot${config.pulse ? " connection-dot-pulse" : ""}`}
        style={{ backgroundColor: config.color }}
        aria-hidden
      />
      <span className="connection-label">{config.label}</span>
    </div>
  );
}
