/**
 * JSON-RPC WebSocket IPC client for communicating with the Python backend server.
 *
 * Usage:
 *   const client = new IpcClient();
 *   await client.connect(8765);
 *   const result = await client.call("some_method", { key: "value" });
 *   client.on("some_event", (data) => console.log(data));
 *   client.disconnect();
 */

type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: unknown;
};

type JsonRpcResponse = {
  jsonrpc: "2.0";
  id?: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
  method?: string;
  params?: unknown;
  /** Server-sent event name (Python server uses {event, data} format) */
  event?: string;
  /** Server-sent event payload (Python server uses {event, data} format) */
  data?: unknown;
};

type EventCallback = (data: unknown) => void;

export class IpcClient {
  private ws: WebSocket | null = null;
  private nextId = 1;
  private pending = new Map<
    number,
    { resolve: (value: unknown) => void; reject: (reason: unknown) => void }
  >();
  private eventListeners = new Map<string, Set<EventCallback>>();
  private port: number | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private shouldReconnect = false;

  /** Connect to the Python WebSocket server at ws://localhost:{port}/ws */
  connect(port: number): Promise<void> {
    this.port = port;
    this.shouldReconnect = true;
    return this._open();
  }

  private _open(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.port) {
        reject(new Error("No port configured"));
        return;
      }

      const url = `ws://localhost:${this.port}/ws`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        this.ws = ws;
        this.reconnectDelay = 1000;
        resolve();
      };

      ws.onerror = (event) => {
        reject(new Error(`WebSocket error: ${JSON.stringify(event)}`));
      };

      ws.onclose = () => {
        this.ws = null;
        this._rejectAllPending(new Error("WebSocket closed"));
        if (this.shouldReconnect) {
          this._scheduleReconnect();
        }
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        this._handleMessage(event.data);
      };
    });
  }

  private _scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._open().catch(() => {
        // Will retry via onclose handler
      });
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(
      this.reconnectDelay * 2,
      this.maxReconnectDelay,
    );
  }

  private _handleMessage(raw: string): void {
    let msg: JsonRpcResponse;
    try {
      msg = JSON.parse(raw) as JsonRpcResponse;
    } catch {
      console.error("[ipc] Failed to parse message:", raw);
      return;
    }

    // Server-sent notification (event)
    // Support both JSON-RPC notification format {method, params}
    // and Python server format {event, data}
    const eventName = msg.method ?? msg.event;
    const eventData = msg.method !== undefined ? msg.params : msg.data;
    if (eventName !== undefined && msg.id === undefined) {
      const listeners = this.eventListeners.get(eventName);
      if (listeners) {
        for (const cb of listeners) {
          cb(eventData);
        }
      }
      return;
    }

    // Response to a pending call
    if (msg.id !== undefined) {
      const pending = this.pending.get(msg.id);
      if (!pending) return;
      this.pending.delete(msg.id);
      if (msg.error) {
        pending.reject(
          new Error(`[${msg.error.code}] ${msg.error.message}`),
        );
      } else {
        pending.resolve(msg.result);
      }
    }
  }

  private _rejectAllPending(error: Error): void {
    for (const [, pending] of this.pending) {
      pending.reject(error);
    }
    this.pending.clear();
  }

  /** Call a JSON-RPC method on the Python server */
  call(method: string, params?: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        reject(new Error("WebSocket is not connected"));
        return;
      }
      const id = this.nextId++;
      const request: JsonRpcRequest = {
        jsonrpc: "2.0",
        id,
        method,
        params,
      };
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify(request));
    });
  }

  /** Subscribe to a server-sent event */
  on(event: string, callback: EventCallback): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    this.eventListeners.get(event)!.add(callback);
  }

  /** Unsubscribe from a server-sent event */
  off(event: string, callback: EventCallback): void {
    this.eventListeners.get(event)?.delete(callback);
  }

  /** Disconnect and stop reconnecting */
  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  /** Manually trigger a reconnect attempt */
  reconnect(): Promise<void> {
    this.ws?.close();
    this.ws = null;
    return this._open();
  }

  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

/** Singleton IPC client instance */
export const ipcClient = new IpcClient();
