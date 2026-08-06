import { readFile } from "node:fs/promises";

export class MemoryStorage {
  #values = new Map();

  get length() {
    return this.#values.size;
  }

  clear() {
    this.#values.clear();
  }

  getItem(key) {
    const normalizedKey = String(key);
    return this.#values.has(normalizedKey) ? this.#values.get(normalizedKey) : null;
  }

  key(index) {
    return [...this.#values.keys()][index] ?? null;
  }

  removeItem(key) {
    this.#values.delete(String(key));
  }

  setItem(key, value) {
    this.#values.set(String(key), String(value));
  }
}

class TestWindow extends EventTarget {
  constructor(fetchImpl) {
    super();
    this.location = {
      origin: "https://app.weave.test",
      pathname: "/dashboard",
    };
    this.fetch = fetchImpl;
    this.__timers = new Map();
    this.__nextTimerId = 1;
  }

  setTimeout(callback, delay) {
    const timerId = this.__nextTimerId;
    this.__nextTimerId += 1;
    this.__timers.set(timerId, { callback, delay });
    return timerId;
  }

  clearTimeout(timerId) {
    this.__timers.delete(timerId);
  }
}

class TestCustomEvent extends Event {
  constructor(type, options = {}) {
    super(type, options);
    this.detail = options.detail;
  }
}

export function installBrowserHarness({ fetchImpl = async () => jsonResponse(200, {}) } = {}) {
  const local = new MemoryStorage();
  const session = new MemoryStorage();
  const testWindow = new TestWindow(fetchImpl);

  globalThis.localStorage = local;
  globalThis.sessionStorage = session;
  globalThis.window = testWindow;
  globalThis.fetch = fetchImpl;
  globalThis.CustomEvent = globalThis.CustomEvent || TestCustomEvent;
  globalThis.__VITE_ENV__ = {
    MODE: "test",
    VITE_API_URL: "https://api.weave.test/api/v1",
  };

  return {
    localStorage: local,
    sessionStorage: session,
    window: testWindow,
    setFetch(nextFetch) {
      globalThis.fetch = nextFetch;
      testWindow.fetch = nextFetch;
    },
  };
}

export function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...headers,
    },
  });
}

export async function importFreshApi() {
  const sourceUrl = new URL("../../src/services/api.js", import.meta.url);
  const originalSource = await readFile(sourceUrl, "utf8");
  const browserCompatibleSource = originalSource.replaceAll(
    "import.meta.env",
    "globalThis.__VITE_ENV__",
  );
  const encodedSource = Buffer.from(
    `${browserCompatibleSource}\n//# sourceURL=weave-api-under-test-${Date.now()}-${Math.random()}.js`,
  ).toString("base64");

  return import(`data:text/javascript;base64,${encodedSource}`);
}

export function createJwt(payload) {
  const encode = (value) =>
    Buffer.from(JSON.stringify(value))
      .toString("base64url")
      .replace(/=/g, "");

  return `${encode({ alg: "none", typ: "JWT" })}.${encode(payload)}.`;
}
