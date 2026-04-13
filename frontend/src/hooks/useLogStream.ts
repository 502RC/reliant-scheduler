import { useState, useEffect, useRef, useCallback } from "react";
import { acquireAccessToken, AUTH_DISABLED } from "@/services/auth";
import type { RunStatus } from "@/types/api";

const MAX_LINES = 10000;
const LOAD_MORE_CHUNK = 5000;

interface UseLogStreamResult {
  lines: string[];
  totalLines: number;
  loading: boolean;
  error: string | null;
  streaming: boolean;
  truncated: boolean;
  loadMore: () => void;
}

/**
 * Log streaming hook that uses SSE for active runs and REST fetch for completed runs.
 *
 * - For running jobs: connects to SSE endpoint for live streaming
 * - For completed jobs: fetches full log via REST and paginates
 * - Handles ANSI escape codes at render time (in the component)
 */
export function useLogStream(
  jobId: string | undefined,
  runId: string | undefined,
  runStatus: RunStatus | undefined,
  logUrl: string | null | undefined
): UseLogStreamResult {
  const [allLines, setAllLines] = useState<string[]>([]);
  const [visibleCount, setVisibleCount] = useState(MAX_LINES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // SSE streaming for active runs
  useEffect(() => {
    if (!jobId || !runId) return;
    if (runStatus !== "running" && runStatus !== "queued" && runStatus !== "pending") return;

    let cancelled = false;
    setStreaming(true);
    setError(null);

    async function connectSSE() {
      let sseUrl = `/api/jobs/${jobId}/runs/${runId}/logs/stream`;

      if (!AUTH_DISABLED) {
        try {
          const token = await acquireAccessToken();
          if (token) {
            sseUrl += `?token=${encodeURIComponent(token)}`;
          }
        } catch { /* proceed without token */ }
      }

      if (cancelled) return;

      const es = new EventSource(sseUrl);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        if (cancelled) return;
        const newLines = event.data.split("\n");
        setAllLines((prev) => {
          const combined = [...prev, ...newLines];
          return combined.length > MAX_LINES * 2 ? combined.slice(-MAX_LINES * 2) : combined;
        });
      };

      es.addEventListener("complete", () => {
        setStreaming(false);
        es.close();
      });

      es.onerror = () => {
        if (cancelled) return;
        // EventSource auto-reconnects for most errors.
        // If the connection is permanently failed, the readyState becomes CLOSED.
        if (es.readyState === EventSource.CLOSED) {
          setStreaming(false);
          // Fall back to REST fetch
          fetchLogRest();
        }
      };
    }

    async function fetchLogRest() {
      if (!logUrl) return;
      setLoading(true);
      try {
        const token = await acquireAccessToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const response = await fetch(logUrl, { headers });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const text = await response.text();
        if (!cancelled) {
          setAllLines(text.split("\n"));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load logs");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    connectSSE();

    return () => {
      cancelled = true;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setStreaming(false);
    };
  }, [jobId, runId, runStatus, logUrl]);

  // REST fetch for completed runs (when SSE is not applicable)
  useEffect(() => {
    if (!logUrl) return;
    if (runStatus === "running" || runStatus === "queued" || runStatus === "pending") return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    async function fetchLog() {
      try {
        const token = await acquireAccessToken();
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const apiLogUrl = "/api/jobs/" + jobId + "/runs/" + runId + "/logs/stream"; const response = await fetch(apiLogUrl, { headers });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const text = await response.text();
        if (!cancelled) {
          setAllLines(text.split("\n"));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load logs");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchLog();
    return () => { cancelled = true; };
  }, [logUrl, runStatus]);

  const truncated = allLines.length > visibleCount;
  const lines = truncated ? allLines.slice(-visibleCount) : allLines;

  const loadMore = useCallback(() => {
    setVisibleCount((prev) => prev + LOAD_MORE_CHUNK);
  }, []);

  return {
    lines,
    totalLines: allLines.length,
    loading,
    error,
    streaming,
    truncated,
    loadMore,
  };
}
