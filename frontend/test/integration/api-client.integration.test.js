import assert from "node:assert/strict";
import test from "node:test";

import {
  importFreshApi,
  installBrowserHarness,
  jsonResponse,
} from "../support/browserHarness.js";

test("an authenticated request refreshes once after 401 and retries with the new token", async () => {
  const calls = [];
  let profileRequestCount = 0;
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url: String(url), init });

    if (String(url).endsWith("/auth/refresh")) {
      return jsonResponse(200, { access_token: "new-access-token" });
    }

    if (String(url).endsWith("/students/me")) {
      profileRequestCount += 1;
      return profileRequestCount === 1
        ? jsonResponse(401, { detail: "expired" })
        : jsonResponse(200, { id: "student-1", first_name: "Grace" });
    }

    throw new Error(`Unexpected request: ${url}`);
  };

  const harness = installBrowserHarness({ fetchImpl });
  const { api, authSession } = await importFreshApi();
  authSession.setToken("old-access-token", { remember: false });

  const profile = await api.get("/students/me");

  assert.deepEqual(profile, { id: "student-1", first_name: "Grace" });
  assert.equal(calls.length, 3);
  assert.equal(calls[0].init.headers.Authorization, "Bearer old-access-token");
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[1].url, "https://api.weave.test/api/v1/auth/refresh");
  assert.equal(calls[1].init.credentials, "include");
  assert.equal(calls[1].init.headers, undefined);
  assert.equal(calls[2].init.headers.Authorization, "Bearer new-access-token");
  assert.equal(harness.sessionStorage.getItem("access_token"), "new-access-token");
});

test("concurrent 401 responses share one refresh request", async () => {
  const attempts = new Map();
  let refreshCalls = 0;
  let releaseRefresh;
  const refreshResponse = new Promise((resolve) => {
    releaseRefresh = () => resolve(jsonResponse(200, { access_token: "shared-token" }));
  });

  const fetchImpl = async (url) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/auth/refresh")) {
      refreshCalls += 1;
      return refreshResponse;
    }

    const count = (attempts.get(pathname) || 0) + 1;
    attempts.set(pathname, count);
    return count === 1
      ? jsonResponse(401, { detail: "expired" })
      : jsonResponse(200, { pathname });
  };

  installBrowserHarness({ fetchImpl });
  const { api, authSession } = await importFreshApi();
  authSession.setToken("expired-token", { remember: true });

  const first = api.get("/students/me");
  const second = api.get("/teachers/me");
  await new Promise((resolve) => setImmediate(resolve));
  releaseRefresh();

  const [student, teacher] = await Promise.all([first, second]);

  assert.equal(refreshCalls, 1);
  assert.equal(student.pathname, "/api/v1/students/me");
  assert.equal(teacher.pathname, "/api/v1/teachers/me");
});

test("JSON and multipart requests preserve the backend transport contract", async () => {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    return jsonResponse(200, { ok: true });
  };

  installBrowserHarness({ fetchImpl });
  const { api } = await importFreshApi();

  await api.post(
    "/auth/login",
    { identifier: "admin@example.com", password: "secret" },
    { auth: false, skipAuthRefresh: true },
  );
  const formData = new FormData();
  formData.set("file", new Blob(["student data"]), "students.csv");
  await api.postForm("/tenant-admin/bulk-imports/students", formData);

  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    identifier: "admin@example.com",
    password: "secret",
  });
  assert.equal(calls[1].init.body, formData);
  assert.equal(new Headers(calls[1].init.headers).has("content-type"), false);
});

test("maintenance responses persist control state and navigate away from protected UI", async () => {
  const fetchImpl = async () =>
    jsonResponse(503, {
      maintenance_mode: true,
      detail: "Scheduled platform maintenance",
      maintenance_reason: "database-upgrade",
    });

  const harness = installBrowserHarness({ fetchImpl });
  const { api, APP_NAVIGATE_EVENT, getStoredMaintenanceState } = await importFreshApi();
  let navigation;
  harness.window.addEventListener(APP_NAVIGATE_EVENT, (event) => {
    navigation = event.detail;
  });

  await assert.rejects(() => api.get("/students/me"), /Scheduled platform maintenance/);

  assert.equal(getStoredMaintenanceState().reason, "database-upgrade");
  assert.deepEqual(navigation, { path: "/maintenance" });
});

test("a failed refresh clears the session and dispatches login navigation", async () => {
  const fetchImpl = async (url) => {
    if (String(url).endsWith("/auth/refresh")) {
      return jsonResponse(401, { detail: "refresh expired" });
    }
    return jsonResponse(401, { detail: "access expired" });
  };

  const harness = installBrowserHarness({ fetchImpl });
  const { api, authSession, APP_NAVIGATE_EVENT } = await importFreshApi();
  authSession.setToken("expired-token", { remember: false });
  authSession.setUser({ id: "student-1", role: "student" }, { remember: false });
  let navigation;
  harness.window.addEventListener(APP_NAVIGATE_EVENT, (event) => {
    navigation = event.detail;
  });

  await assert.rejects(() => api.get("/students/me"), /refresh expired/);

  assert.equal(authSession.getToken(), null);
  assert.equal(authSession.getUser(), null);
  assert.deepEqual(navigation, { path: "/login" });
});
