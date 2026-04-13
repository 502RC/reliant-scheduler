import { useRef, useEffect, useState, useCallback } from "react";
import { useLogStream } from "@/hooks/useLogStream";
import { parseAnsiLine, stripAnsi } from "@/utils/ansi";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import type { RunStatus } from "@/types/api";

interface LogViewerProps {
  jobId: string;
  runId: string;
  runStatus: RunStatus;
  logUrl: string | null;
}

export default function LogViewer({ jobId, runId, runStatus, logUrl }: LogViewerProps) {
  const { lines, totalLines, loading, error, streaming, truncated, loadMore } = useLogStream(
    jobId,
    runId,
    runStatus,
    logUrl
  );
  const [follow, setFollow] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(follow);
  followRef.current = follow;

  // Auto-scroll when follow is enabled and new lines arrive
  useEffect(() => {
    if (followRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines.length]);

  // Detect manual scroll to auto-disable follow
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (follow !== atBottom) {
      setFollow(atBottom);
    }
  }, [follow]);

  const handleDownload = useCallback(() => {
    const text = lines.map(stripAnsi).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `job-${jobId}-run-${runId}.log`;
    a.click();
    URL.revokeObjectURL(url);
  }, [lines, jobId, runId]);

  if (!logUrl && !streaming && runStatus !== "running") {
    return (
      <div className="card" style={{ padding: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Execution Log</h3>
        <p style={{ color: "#6b7280", fontSize: 13 }}>No log URL available for this run.</p>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="log-viewer-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600 }}>Execution Log</h3>
          {streaming && (
            <span className="log-streaming-badge">
              <span className="log-streaming-dot" aria-hidden />
              Streaming
            </span>
          )}
          {totalLines > 0 && (
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {totalLines.toLocaleString()} lines
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label
            style={{
              fontSize: 12,
              color: "#6b7280",
              display: "flex",
              alignItems: "center",
              gap: 4,
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={follow}
              onChange={(e) => setFollow(e.target.checked)}
            />
            Follow
          </label>
          <button className="btn btn-sm btn-secondary" onClick={handleDownload} disabled={lines.length === 0}>
            Download
          </button>
        </div>
      </div>

      {truncated && (
        <div className="log-truncation-bar">
          <span>Showing last {lines.length.toLocaleString()} of {totalLines.toLocaleString()} lines</span>
          <button className="btn btn-sm btn-secondary" onClick={loadMore}>
            Load more
          </button>
        </div>
      )}

      {loading && lines.length === 0 ? (
        <div style={{ padding: 24 }}>
          <LoadingSpinner message="Loading logs..." size={24} />
        </div>
      ) : error ? (
        <div style={{ padding: 16, color: "#dc2626", fontSize: 13 }}>
          Failed to load logs: {error}
        </div>
      ) : (
        <div
          ref={containerRef}
          className="log-viewer-content"
          onScroll={handleScroll}
          role="log"
          aria-label="Job execution log"
        >
          {lines.length === 0 ? (
            <span style={{ color: "#6b7280" }}>No log output yet.</span>
          ) : (
            lines.map((line, i) => <LogLine key={i} line={line} lineNumber={i + 1} />)
          )}
        </div>
      )}
    </div>
  );
}

function LogLine({ line, lineNumber }: { line: string; lineNumber: number }) {
  const spans = parseAnsiLine(line);
  return (
    <div className="log-line">
      <span className="log-line-number" aria-hidden>
        {lineNumber}
      </span>
      <span className="log-line-text">
        {spans.map((span, i) =>
          span.style ? (
            <span key={i} style={parseInlineStyle(span.style)}>
              {span.text}
            </span>
          ) : (
            <span key={i}>{span.text}</span>
          )
        )}
      </span>
    </div>
  );
}

function parseInlineStyle(styleStr: string): React.CSSProperties {
  const obj: Record<string, string> = {};
  for (const part of styleStr.split(";")) {
    const [key, value] = part.split(":");
    if (key && value) {
      // Convert CSS property names to camelCase
      const camelKey = key.trim().replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
      obj[camelKey] = value.trim();
    }
  }
  return obj as unknown as React.CSSProperties;
}
