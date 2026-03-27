import { useEffect, useRef, useCallback } from "react";
import { supabase } from "../lib/supabase";
import type { TransformJobMessage, TransformWsOutgoing } from "../types/transform";

interface UseTransformWebSocketOptions {
  projectId: string | null;
  onMessage: (msg: TransformJobMessage) => void;
}

const MAX_RECONNECT_DELAY = 16_000;
const HEARTBEAT_INTERVAL = 30_000;

export function useTransformWebSocket({ projectId, onMessage }: UseTransformWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const cleanup = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((msg: TransformWsOutgoing) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const cancelJob = useCallback((jobId: string) => {
    sendMessage({ type: "cancel", job_id: jobId });
  }, [sendMessage]);

  useEffect(() => {
    if (!projectId) return;

    let isMounted = true;

    async function connect() {
      // Get auth token
      let token = "";
      if (supabase) {
        const { data: { session } } = await supabase.auth.getSession();
        token = session?.access_token ?? "";
      }

      if (!isMounted) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
      const url = `${protocol}//${host}/api/v1/ws/transforms/${projectId}${tokenParam}`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectDelay.current = 1000; // reset on successful connection

        // Start heartbeat
        heartbeatTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as TransformJobMessage | { type: string };
          if (data.type === "pong") return;
          onMessageRef.current(data as TransformJobMessage);
        } catch {
          // ignore unparseable messages
        }
      };

      ws.onclose = () => {
        if (heartbeatTimer.current) {
          clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }

        if (!isMounted) return;

        // Reconnect with exponential backoff
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, MAX_RECONNECT_DELAY);
          connect();
        }, reconnectDelay.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      isMounted = false;
      cleanup();
    };
  }, [projectId, cleanup]);

  return { cancelJob };
}
