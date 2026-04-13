interface Props {
  size?: number;
  message?: string;
}

export default function LoadingSpinner({ size = 32, message }: Props) {
  return (
    <div style={styles.wrapper} role="status" aria-label="Loading">
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        style={styles.spinner}
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="#e5e7eb"
          strokeWidth="3"
        />
        <path
          d="M12 2a10 10 0 0 1 10 10"
          stroke="#3b82f6"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      {message && <p style={styles.message}>{message}</p>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: 40,
    gap: 12,
  },
  spinner: {
    animation: "spin 1s linear infinite",
  },
  message: {
    margin: 0,
    color: "#6b7280",
    fontSize: 14,
  },
};
