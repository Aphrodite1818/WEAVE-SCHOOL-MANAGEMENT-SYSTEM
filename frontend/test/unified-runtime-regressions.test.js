
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("unverified login requests one OTP after redirect", async () => {
  const login = await read("src/pages/public/LoginPage.jsx");
  const otp = await read("src/pages/public/otp_validationPage.jsx");
  assert.match(login, /autoRequestOtp: true/);
  assert.match(login, /source: "unverified-login"/);
  assert.match(otp, /automaticRequestKeyRef/);
  assert.match(otp, /authService[\s\S]*\.requestOtp\(email, purpose\)/);
});

test("dashboard pull refresh revalidates without restarting the document", async () => {
  const layout = await read("src/components/layout/DashboardLayout.jsx");
  const cache = await read("src/services/dashboardSessionCache.js");
  assert.match(layout, /weave:pull-refresh/);
  assert.doesNotMatch(layout, /window\.location\.reload/);
  assert.match(cache, /sessionStorage/);
  assert.doesNotMatch(cache, /beforeunload/);
});

test("commercial pricing is backend-owned and conditionally revalidated", async () => {
  const config = await read("src/features/subscriptions/subscriptionConfig.js");
  const service = await read("src/services/subscriptionService.js");
  assert.doesNotMatch(config, /15000|35000|80000|₦15,000|₦35,000|₦80,000/);
  assert.match(service, /If-None-Match/);
  assert.match(service, /status === 304/);
  assert.match(service, /cache: "no-cache"/);
});

test("application routes are code split", async () => {
  const routes = await Promise.all([
    read("src/routes/publicRoutes.jsx"),
    read("src/routes/adminRoutes.jsx"),
    read("src/routes/teacherRoutes.jsx"),
    read("src/routes/studentRoutes.jsx"),
    read("src/routes/parentRoutes.jsx"),
    read("src/routes/superadminRoutes.jsx"),
  ]);
  routes.forEach((source) => assert.match(source, /lazy\(\(\) => import\(/));
  const index = await read("src/routes/index.jsx");
  assert.match(index, /Suspense/);
});
