import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface Props {
  title: string;
  description?: string;
  action?: ReactNode;
  actionLabel?: string;
  actionTo?: string;
  actionOnClick?: () => void;
}

export default function EmptyState({ title, description, action, actionLabel, actionTo, actionOnClick }: Props) {
  return (
    <div style={styles.container}>
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" aria-hidden>
        <rect
          x="3"
          y="3"
          width="18"
          height="18"
          rx="3"
          stroke="#d1d5db"
          strokeWidth="1.5"
        />
        <path d="M9 9h6M9 13h4" stroke="#d1d5db" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <h3 style={styles.title}>{title}</h3>
      {description && <p style={styles.description}>{description}</p>}
      {action && <div style={styles.action}>{action}</div>}
      {actionLabel && actionTo && (
        <div style={styles.action}>
          <Link to={actionTo} className="btn btn-primary">{actionLabel}</Link>
        </div>
      )}
      {actionLabel && actionOnClick && !actionTo && (
        <div style={styles.action}>
          <button className="btn btn-primary" onClick={actionOnClick}>{actionLabel}</button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: 48,
    gap: 8,
    textAlign: "center",
  },
  title: { margin: 0, fontSize: 16, fontWeight: 600, color: "#374151" },
  description: { margin: 0, fontSize: 14, color: "#6b7280", maxWidth: 360 },
  action: { marginTop: 8 },
};
