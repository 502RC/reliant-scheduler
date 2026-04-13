import type { RunStatus } from "@/types/api";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function formatDuration(
  start: string | null | undefined,
  end: string | null | undefined
): string {
  if (!start) return "—";
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const diffMs = endDate.getTime() - startDate.getTime();
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainSec = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainSec}s`;
  const hours = Math.floor(minutes / 60);
  const remainMin = minutes % 60;
  return `${hours}h ${remainMin}m`;
}

const JOB_STATUS_LABELS: Record<string, string> = {
  active: "Ready",
  inactive: "Disabled",
  paused: "Paused",
  archived: "Archived",
};

const STATUS_LABELS: Record<RunStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  running: "Running",
  success: "Success",
  failed: "Failed",
  cancelled: "Cancelled",
  timed_out: "Timed Out",
};

export function statusLabel(status: RunStatus): string {
  return JOB_STATUS_LABELS[status] ?? STATUS_LABELS[status as RunStatus] ?? status;
}

const STATUS_COLORS: Record<RunStatus, string> = {
  pending: "#6b7280",
  queued: "#8b5cf6",
  running: "#3b82f6",
  success: "#10b981",
  failed: "#ef4444",
  cancelled: "#9ca3af",
  timed_out: "#f59e0b",
};

export function statusColor(status: RunStatus): string {
  return STATUS_COLORS[status] ?? "#6b7280";
}
