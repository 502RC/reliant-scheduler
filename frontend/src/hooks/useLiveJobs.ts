import { useEffect, useCallback, useRef } from "react";
import { useEventBus } from "@/services/eventBus";
import type { WsEvent, WsJobStatusPayload } from "@/types/api";

/**
 * Hook that triggers a refetch callback when job status events arrive.
 * Debounces rapid bursts to avoid excessive API calls.
 */
export function useLiveRefresh(refetch: () => void, debounceMs = 1000) {
  const { subscribe, connectionStatus } = useEventBus();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  const debouncedRefetch = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      refetchRef.current();
    }, debounceMs);
  }, [debounceMs]);

  useEffect(() => {
    if (connectionStatus !== "connected") return;

    const unsub = subscribe((event: WsEvent) => {
      if (
        event.type === "job.status_changed" ||
        event.type === "job.started" ||
        event.type === "job.completed" ||
        event.type === "job.failed" ||
        event.type === "job.timed_out" ||
        event.type === "agent.status_changed"
      ) {
        debouncedRefetch();
      }
    });

    return () => {
      unsub();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [subscribe, connectionStatus, debouncedRefetch]);
}

/**
 * Hook that calls a handler when a specific job's status changes.
 */
export function useJobStatusEvent(
  jobId: string | undefined,
  onStatusChange: (payload: WsJobStatusPayload) => void
) {
  const { subscribe, connectionStatus } = useEventBus();
  const handlerRef = useRef(onStatusChange);
  handlerRef.current = onStatusChange;

  useEffect(() => {
    if (!jobId || connectionStatus !== "connected") return;

    const unsub = subscribe((event: WsEvent) => {
      if (
        (event.type === "job.status_changed" ||
          event.type === "job.started" ||
          event.type === "job.completed" ||
          event.type === "job.failed" ||
          event.type === "job.timed_out") &&
        (event.payload as WsJobStatusPayload).job_id === jobId
      ) {
        handlerRef.current(event.payload as WsJobStatusPayload);
      }
    });

    return unsub;
  }, [jobId, subscribe, connectionStatus]);
}
