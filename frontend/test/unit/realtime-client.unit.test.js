import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { installBrowserHarness } from "../support/browserHarness.js";

class FakeWebSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.listeners = new Map();
    this.sent = [];
    this.closeCalls = [];
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type, callback) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(callback);
  }

  emit(type, payload = {}) {
    for (const callback of this.listeners.get(type) || []) callback(payload);
  }

  open() {
    this.readyState = 1;
    this.emit("open");
  }

  receive(message) {
    this.emit("message", { data: JSON.stringify(message) });
  }

  send(payload) {
    this.sent.push(JSON.parse(payload));
  }

  close(code, reason) {
    this.readyState = 3;
    this.closeCalls.push({ code, reason });
  }

  serverClose(code = 1006) {
    this.readyState = 3;
    this.emit("close", { code });
  }
}

const importRealtimeClient = async () => {
  const sourceUrl = new URL("../../src/services/realtimeClient.js", import.meta.url);
  const source = await readFile(sourceUrl, "utf8");
  const isolatedSource = source
    .replace(
      'import { API_BASE_URL, authSession } from "./api";',
      'const API_BASE_URL = "https://api.weave.test/api/v1";\n' +
        "const authSession = { getToken: () => null, subscribeToken: () => () => {} };",
    )
    .replace(
      /import\s*\{\s*markConnectionReady,\s*resetAuthenticationLifecycle,\s*\}\s*from\s*"\.\/realtimeClientState";/,
      "const resetAuthenticationLifecycle = (client) => { client.authenticatedOnce = false; client.reconnectAttempt = 0; client.lastAuthenticatedToken = null; };\n" +
        "const markConnectionReady = (client) => { const status = client.authenticatedOnce ? 'reconnected' : 'ready'; client.authenticatedOnce = true; return status; };",
    );
  const encoded = Buffer.from(isolatedSource).toString("base64");
  return import(`data:text/javascript;base64,${encoded}#${Date.now()}-${Math.random()}`);
};

const setup = async () => {
  FakeWebSocket.instances = [];
  const harness = installBrowserHarness();
  harness.window.setInterval = harness.window.setTimeout.bind(harness.window);
  harness.window.clearInterval = harness.window.clearTimeout.bind(harness.window);
  const { RealtimeClient } = await importRealtimeClient();
  let token = "token-one";
  let tokenListener = null;
  const client = new RealtimeClient({
    url: "wss://api.weave.test/api/v1/realtime/stream",
    WebSocketImpl: FakeWebSocket,
    getToken: () => token,
    subscribeToken: (listener) => {
      tokenListener = listener;
      return () => {
        tokenListener = null;
      };
    },
  });
  return {
    client,
    harness,
    RealtimeClient,
    setToken(nextToken) {
      token = nextToken;
      tokenListener?.(nextToken);
    },
  };
};

test("realtime client authenticates once and waits for connection.ready", async () => {
  const { client } = await setup();
  client.start();
  client.start();

  assert.equal(FakeWebSocket.instances.length, 1);
  const socket = FakeWebSocket.instances[0];
  socket.open();
  assert.deepEqual(socket.sent, [{ type: "auth", access_token: "token-one" }]);
  assert.equal(client.ready, false);

  socket.receive({ type: "connection.ready", connection_id: "connection-1" });
  assert.equal(client.ready, true);
});

test("realtime client dispatches to multiple listeners and supports unsubscribe", async () => {
  const { client } = await setup();
  const received = [];
  const unsubscribeFirst = client.subscribe("notification.created", (event) =>
    received.push(["first", event.data.id]),
  );
  client.subscribe("notification.created", (event) =>
    received.push(["second", event.data.id]),
  );
  client.start();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.receive({ type: "connection.ready" });
  socket.receive({ type: "notification.created", data: { id: "one" } });
  unsubscribeFirst();
  socket.receive({ type: "notification.created", data: { id: "two" } });

  assert.deepEqual(received, [
    ["first", "one"],
    ["second", "one"],
    ["second", "two"],
  ]);
});

test("HTTP token rotation propagates through auth.refresh and logout closes the socket", async () => {
  const { client, setToken } = await setup();
  client.start();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.receive({ type: "connection.ready" });

  setToken("token-two");
  assert.deepEqual(socket.sent.at(-1), {
    type: "auth.refresh",
    access_token: "token-two",
  });

  setToken(null);
  assert.deepEqual(socket.closeCalls, [{ code: 1000, reason: "Logged out" }]);
  assert.equal(client.socket, null);
});

test("a fresh login after logout emits ready instead of reconnected", async () => {
  const { client, setToken } = await setup();
  const states = [];
  client.subscribeConnection((state) => states.push(state.status));
  client.start();
  const first = FakeWebSocket.instances[0];
  first.open();
  first.receive({ type: "connection.ready" });

  setToken(null);
  setToken("token-two");
  const second = FakeWebSocket.instances[1];
  second.open();
  second.receive({ type: "connection.ready" });

  assert.deepEqual(states, ["ready", "ready"]);
});

test("unexpected disconnect uses one bounded reconnect timer", async () => {
  const { client, harness } = await setup();
  client.start();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.receive({ type: "connection.ready" });
  socket.serverClose(1006);

  assert.equal(FakeWebSocket.instances.length, 1);
  assert.equal(harness.window.__timers.size, 1);
  const [{ callback, delay }] = [...harness.window.__timers.values()];
  assert.ok(delay >= 800 && delay <= 1200);
  callback();
  assert.equal(FakeWebSocket.instances.length, 2);
});

test("authentication close waits for a new token instead of reconnecting in a storm", async () => {
  const { client, harness, setToken } = await setup();
  client.start();
  const socket = FakeWebSocket.instances[0];
  socket.open();
  socket.serverClose(4401);

  assert.equal(harness.window.__timers.size, 0);
  setToken("token-two");
  assert.equal(FakeWebSocket.instances.length, 2);
});

test("WebSocket construction failure cannot interrupt the REST application", async () => {
  const { RealtimeClient, harness } = await setup();
  class RejectedWebSocket {
    constructor() {
      throw new DOMException("Blocked by browser policy", "SecurityError");
    }
  }
  const client = new RealtimeClient({
    url: "wss://api.weave.test/api/v1/realtime/stream",
    WebSocketImpl: RejectedWebSocket,
    getToken: () => "token-one",
    subscribeToken: () => () => {},
  });

  assert.doesNotThrow(() => client.start());
  assert.equal(harness.window.__timers.size, 1);
});
