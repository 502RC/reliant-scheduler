import { useState, useEffect, useRef, useCallback } from "react";
import type { WsEvent, WsConnectionStatus } from "@/types/api";
import { acquireAccessToken, AUTH_DISABLED } from "@/services/auth";

const INITIAL_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 30000;
const HEARTBEAT_TIMEOUT_MS = 10000;

interface UseWebSocketOptions {
  /** Override the WebSocket URL. Defaults to `ws(s)://<host>/ws/events`. */
  url?: string;
  /** Disable auto-connect. */
  enabled?: boolean;
}

interface UseWebSocketResult {
  status: WsConnectionStatus;
  lastEvent: WsEvent | null;
  subscribe: (handler: (event: WsEvent) => void) => () => void;
}

/**
 * Persistent WebSocket connection to /ws/events with:
 * - Auto-reconnect with exponential backoff
 * - Heartbeat ping/pong for stale connection detection
 * - Bearer token authentication via query param
 * - Subscriber pattern for distributing events
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketResult {
  const { url, enabled = true } = options;
  const [status, setStatus] = useState<WsConnectionStatus>("disconnected");
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const subscribersRef = useRef<Set<(event: WsEvent) => void>>(new Set());
  const enabledRef = useRef(enabled);

  enabledRef.current = enabled;

  const subscribe = useCallback((handler: (event: WsEvent) => void) => {
    subscribersRef.current.add(handler);
    return () => {
      subscribersRef.current.delete(handler);
    };
  }, []);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!enabledRef.current) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    clearTimers();

    setStatus("connecting");

    // Build WebSocket URL
    let wsUrl: string;
    if (url) {
      wsUrl = url;
    } else {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      wsUrl = `${protocol}//${window.location.host}/ws/events`;
    }

    // Attach token as query param for WebSocket auth
    if (!AUTH_DISABLED) {
      try {
        const token = await acquireAccessToken();
        if (token) {
          const separator = wsUrl.includes("?") ? "&" : "?";
          wsUrl = `${wsUrl}${separator}token=${encodeURIComponent(token)}`;
        }
      } catch {
        // Proceed without token; server will reject if required
      }
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
        reconnectDelayRef.current = INITIAL_RECONNECT_MS;

        // Start heartbeat
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
            // Set timeout for pong response
            heartbeatTimeoutRef.current = setTimeout(() => {
              // No pong received — connection is stale
              ws.close();
            }, HEARTBEAT_TIMEOUT_MS);
          }
        }, HEARTBEAT_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as { type: string } & Record<string, unknown>;

          // Handle pong responses
          if (data.type === "pong") {
            if (heartbeatTimeoutRef.current) {
              clearTimeout(heartbeatTimeoutRef.current);
              heartbeatTimeoutRef.current = null;
            }
            return;
          }

          const wsEvent = data as unknown as WsEvent;
          setLastEvent(wsEvent);

          // Notify all subscribers
          for (const handler of subscribersRef.current) {
            try {
              handler(wsEvent);
            } catch (err) {
              console.error("[WebSocket] Subscriber error:", err);
            }
          }
        } catch {
          console.warn("[WebSocket] Failed to parse message:", event.data);
        }
      };

      ws.onclose = () => {
        clearTimers();
        wsRef.current = null;

        if (!enabledRef.current) {
          setStatus("disconnected");
          return;
        }

        setStatus("reconnecting");
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_MS);
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = () => {
        // onclose will fire after onerror, triggering reconnect
      };
    } catch {
      // WebSocket constructor can throw if URL is invalid
      setStatus("disconnected");
    }
  }, [url, clearTimers]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      clearTimers();
      setStatus("disconnected");
    }

    return () => {
      enabledRef.current = false;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      clearTimers();
    };
  }, [enabled, connect, clearTimers]);

  return { status, lastEvent, subscribe };
}
