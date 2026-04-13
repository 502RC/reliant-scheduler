import { useState, useEffect, useCallback, useRef } from "react";
import { ApiError } from "@/services/api";

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options?: { refetchInterval?: number }
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (mountedRef.current) {
        setData(result);
      }
    } catch (err) {
      if (mountedRef.current) {
        if (err instanceof ApiError) {
          setError(`${err.status}: ${err.message}`);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unexpected error occurred");
        }
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mountedRef.current = true;
    execute();
    return () => {
      mountedRef.current = false;
    };
  }, [execute]);

  useEffect(() => {
    if (!options?.refetchInterval) return;
    const interval = setInterval(async () => {
      if (!mountedRef.current) return;
      try {
        const result = await fetcher();
        if (mountedRef.current) setData(result);
      } catch {
        // Silent fail on background refetch
      }
    }, options.refetchInterval);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options?.refetchInterval, ...deps]);

  return { data, loading, error, refetch: execute };
}
