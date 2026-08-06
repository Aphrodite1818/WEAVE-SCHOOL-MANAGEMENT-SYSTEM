import assert from "node:assert/strict";
import test from "node:test";

import { installBrowserHarness } from "../support/browserHarness.js";

const importFreshGuard = () =>
  import(`../../src/services/installCookieCsrfFetchGuard.js?test=${Date.now()}-${Math.random()}`);

test("cookie-backed refresh and logout POSTs receive the CSRF marker", async () => {
  const calls = [];
  const nativeFetch = async (input, init) => {
    calls.push({ input, init });
    return new Response(null, { status: 204 });
  };
  const harness = installBrowserHarness({ fetchImpl: nativeFetch });
  const { installCookieCsrfFetchGuard } = await importFreshGuard();

  installCookieCsrfFetchGuard();
  await harness.window.fetch("https://api.weave.test/api/v1/auth/refresh", {
    method: "POST",
    headers: { "X-Request-ID": "request-1" },
  });
  await harness.window.fetch("/api/v1/auth/logout", { method: "POST" });

  assert.equal(calls.length, 2);
  assert.equal(new Headers(calls[0].init.headers).get("X-Weave-CSRF"), "1");
  assert.equal(new Headers(calls[0].init.headers).get("X-Request-ID"), "request-1");
  assert.equal(new Headers(calls[1].init.headers).get("X-Weave-CSRF"), "1");
});

test("unprotected requests pass through unchanged and installation is idempotent", async () => {
  const calls = [];
  const nativeFetch = async (input, init) => {
    calls.push({ input, init });
    return new Response(null, { status: 204 });
  };
  const harness = installBrowserHarness({ fetchImpl: nativeFetch });
  const { installCookieCsrfFetchGuard } = await importFreshGuard();

  installCookieCsrfFetchGuard();
  const guardedFetch = harness.window.fetch;
  installCookieCsrfFetchGuard();

  assert.equal(harness.window.fetch, guardedFetch);
  await harness.window.fetch("/api/v1/students/me", { method: "GET" });
  await harness.window.fetch("/api/v1/auth/refresh", { method: "GET" });

  assert.equal(calls.length, 2);
  assert.equal(calls[0].init.headers, undefined);
  assert.equal(calls[1].init.headers, undefined);
});
