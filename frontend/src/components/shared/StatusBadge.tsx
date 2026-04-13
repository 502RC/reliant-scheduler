import type { RunStatus } from "@/types/api";
import { statusLabel, statusColor } from "@/utils/format";

const VARIANT_COLORS: Record<string, string> = {
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
  info: "#3b82f6",
  default: "#6b7280",
};

interface Props {
  status: RunStatus | string;
  variant?: string;
}

export default function StatusBadge({ status, variant }: Props) {
  const color = variant
    ? VARIANT_COLORS[variant] ?? VARIANT_COLORS.default
    : statusColor(status as RunStatus);

  const label = variant
    ? status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : statusLabel(status as RunStatus);

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 500,
        color,
        backgroundColor: `${color}18`,
        border: `1px solid ${color}40`,
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          backgroundColor: color,
          display: "inline-block",
        }}
        aria-hidden
      />
      {label}
    </span>
  );
}
