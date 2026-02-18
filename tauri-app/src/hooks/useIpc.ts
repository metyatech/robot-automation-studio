import { useEffect, useRef, useCallback, useState } from "react";
import { IpcClient, ipcClient } from "@/lib/ipc";

type EventCallback = (data: unknown) => void;

/**
 * React hook wrapping the singleton IPC client.
 * Connects on mount (if a port is provided), disconnects on unmount.
 * Exposes `call` for JSON-RPC methods and `subscribe` for server events.
 */
export function useIpc(port: number | null) {
  const clientRef = useRef<IpcClient>(ipcClient);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (port === null) return;

    let cancelled = false;
    const client = clientRef.current;

    client
      .connect(port)
      .then(() => {
        if (!cancelled) setConnected(true);
      })
      .catch((err) => {
        console.error("[useIpc] connect failed:", err);
      });

    return () => {
      cancelled = true;
      client.disconnect();
      setConnected(false);
    };
  }, [port]);

  const call = useCallback(
    (method: string, params?: unknown): Promise<unknown> => {
      return clientRef.current.call(method, params);
    },
    [],
  );

  const subscribe = useCallback(
    (event: string, callback: EventCallback): (() => void) => {
      clientRef.current.on(event, callback);
      return () => clientRef.current.off(event, callback);
    },
    [],
  );

  return { call, subscribe, connected, client: clientRef.current };
}
