import { API_BASE_URL, authSession } from "./api";

const READY_STATE_CONNECTING = 0;
const READY_STATE_OPEN = 1;
const NORMAL_CLOSE_CODE = 1000;
const AUTHENTICATION_CLOSE_CODES = new Set([4401, 4403]);

const buildRealtimeUrl = (apiBaseUrl = API_BASE_URL) => {
  const baseUrl = new URL(apiBaseUrl, window.location.origin);
  baseUrl.protocol = baseUrl.protocol === "https:" ? "wss:" : "ws:";
  baseUrl.pathname = `${baseUrl.pathname.replace(/\/$/, "")}/realtime/stream`;
  baseUrl.search = "";
  baseUrl.hash = "";
  return baseUrl.toString();
};

export class RealtimeClient {
  constructor({
    url = buildRealtimeUrl(),
    WebSocketImpl = globalThis.WebSocket,
    getToken = () => authSession.getToken(),
    subscribeToken = (listener) => authSession.subscribeToken(listener),
    heartbeatIntervalMs = 25_000,
    maxReconnectDelayMs = 30_000,
  } = {}) {
    this.url = url;
    this.WebSocketImpl = WebSocketImpl;
    this.getToken = getToken;
    this.subscribeToken = subscribeToken;
    this.heartbeatIntervalMs = heartbeatIntervalMs;
    this.maxReconnectDelayMs = maxReconnectDelayMs;
    this.socket = null;
    this.listeners = new Map();
    this.connectionListeners = new Set();
    this.unsubscribeToken = null;
    this.reconnectTimer = null;
    this.heartbeatTimer = null;
    this.reconnectAttempt = 0;
    this.started = false;
    this.ready = false;
    this.authenticatedOnce = false;
    this.intentionalClose = false;
    this.lastAuthenticatedToken = null;
  }

  start() {
    if (this.started) return;
    this.started = true;
    this.unsubscribeToken = this.subscribeToken((token) => this.handleToken(token));
    this.handleToken(this.getToken());
  }

  stop() {
    this.started = false;
    this.intentionalClose = true;
    this.unsubscribeToken?.();
    this.unsubscribeToken = null;
    this.clearReconnectTimer();
    this.stopHeartbeat();
    this.ready = false;

    const socket = this.socket;
    this.socket = null;
    if (
      socket &&
      (socket.readyState === READY_STATE_CONNECTING || socket.readyState === READY_STATE_OPEN)
    ) {
      socket.close(NORMAL_CLOSE_CODE, "Session closed");
    }
  }

  handleToken(token) {
    if (!token) {
      this.disconnectForLogout();
      return;
    }

    if (this.socket?.readyState === READY_STATE_OPEN) {
      if (this.ready) {
        this.lastAuthenticatedToken = token;
        this.send({ type: "auth.refresh", access_token: token });
      }
      return;
    }

    if (this.socket?.readyState === READY_STATE_CONNECTING) return;
    this.connect();
  }

  connect() {
    if (!this.started || !this.getToken() || !this.WebSocketImpl) return;
    if (
      this.socket &&
      (this.socket.readyState === READY_STATE_CONNECTING ||
        this.socket.readyState === READY_STATE_OPEN)
    ) {
      return;
    }

    this.intentionalClose = false;
    this.ready = false;
    let socket;
    try {
      socket = new this.WebSocketImpl(this.url);
    } catch {
      this.emitConnection({ status: "unavailable" });
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;

    socket.addEventListener("open", () => {
      if (socket !== this.socket) return;
      const token = this.getToken();
      if (!token) {
        this.disconnectForLogout();
        return;
      }
      this.lastAuthenticatedToken = token;
      this.send({ type: "auth", access_token: token });
    });

    socket.addEventListener("message", (event) => this.handleMessage(socket, event));
    socket.addEventListener("close", (event) => this.handleClose(socket, event));
    socket.addEventListener("error", () => {
      // The close event owns reconnection. Logging here would duplicate browser noise.
    });
  }

  handleMessage(socket, messageEvent) {
    if (socket !== this.socket) return;

    let message;
    try {
      message = JSON.parse(messageEvent.data);
    } catch {
      return;
    }

    if (message.type === "connection.ready") {
      const reconnected = this.authenticatedOnce;
      this.authenticatedOnce = true;
      this.ready = true;
      this.reconnectAttempt = 0;
      this.startHeartbeat();
      this.emitConnection({ status: reconnected ? "reconnected" : "ready", message });
      const currentToken = this.getToken();
      if (currentToken && currentToken !== this.lastAuthenticatedToken) {
        this.lastAuthenticatedToken = currentToken;
        this.send({ type: "auth.refresh", access_token: currentToken });
      }
      return;
    }

    if (message.type === "pong" || message.type === "auth.refreshed") return;
    if (message.type === "error") {
      this.emitConnection({ status: "error", message });
      return;
    }

    this.emit(message.type, message);
  }

  handleClose(socket, event) {
    if (socket !== this.socket) return;
    this.socket = null;
    this.ready = false;
    this.lastAuthenticatedToken = null;
    this.stopHeartbeat();
    this.emitConnection({ status: "disconnected", code: event.code });

    if (
      this.started &&
      !this.intentionalClose &&
      this.getToken() &&
      !AUTHENTICATION_CLOSE_CODES.has(event.code)
    ) {
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer !== null) return;
    const exponentialDelay = Math.min(
      1_000 * 2 ** this.reconnectAttempt,
      this.maxReconnectDelayMs,
    );
    const jitteredDelay = Math.round(exponentialDelay * (0.8 + Math.random() * 0.4));
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, jitteredDelay);
  }

  disconnectForLogout() {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.stopHeartbeat();
    this.ready = false;
    this.reconnectAttempt = 0;
    const socket = this.socket;
    this.socket = null;
    if (
      socket &&
      (socket.readyState === READY_STATE_CONNECTING || socket.readyState === READY_STATE_OPEN)
    ) {
      socket.close(NORMAL_CLOSE_CODE, "Logged out");
    }
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ready) this.send({ type: "ping" });
    }, this.heartbeatIntervalMs);
  }

  stopHeartbeat() {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  clearReconnectTimer() {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  send(message) {
    if (this.socket?.readyState !== READY_STATE_OPEN) return false;
    this.socket.send(JSON.stringify(message));
    return true;
  }

  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) this.listeners.set(eventType, new Set());
    this.listeners.get(eventType).add(callback);
    return () => {
      const callbacks = this.listeners.get(eventType);
      callbacks?.delete(callback);
      if (callbacks?.size === 0) this.listeners.delete(eventType);
    };
  }

  subscribeConnection(callback) {
    this.connectionListeners.add(callback);
    return () => this.connectionListeners.delete(callback);
  }

  emit(eventType, message) {
    for (const callback of [...(this.listeners.get(eventType) || [])]) {
      try {
        callback(message);
      } catch (error) {
        console.error("Realtime event listener failed", error);
      }
    }
  }

  emitConnection(state) {
    for (const callback of [...this.connectionListeners]) {
      try {
        callback(state);
      } catch (error) {
        console.error("Realtime connection listener failed", error);
      }
    }
  }
}

export const realtimeClient = new RealtimeClient();
