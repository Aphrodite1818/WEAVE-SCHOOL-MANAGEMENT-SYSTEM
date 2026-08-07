import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("installed mobile navigation stays close to the device bottom edge", () => {
  const css = readSource("styles", "mobileOverrides.css");

  assert.match(
    css,
    /bottom:\s*calc\(-0\.45\s*\*\s*env\(safe-area-inset-bottom\)\)\s*!important/,
  );
  assert.match(
    css,
    /calc\(env\(safe-area-inset-bottom\)\s*\*\s*0\.45\)/,
  );
});

test("assisted class-limit warning routes admins to a working checkout page", () => {
  const setupPage = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const plansPage = readSource("pages", "admin", "SubscriptionOptionsPage.jsx");
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  const guideNavigation = readSource("features", "guides", "guideNavigation.js");

  assert.match(setupPage, /detail\?\.reason === "resource_limit_reached"/);
  assert.match(setupPage, /actionLabel:\s*"Upgrade plan"/);
  assert.match(setupRoute, /label === "upgrade plan"/);
  assert.match(setupRoute, /leaveAdminSetup\("\/admin\/billing\/plans"\)/);
  assert.match(guideNavigation, /window\.location\.replace\(destination\)/);
  assert.match(plansPage, /initializeSubscriptionCheckout/);
  assert.match(plansPage, /window\.location\.assign\(response\.authorization_url\)/);
});

test("new tenant admins enter assisted setup immediately after onboarding", () => {
  const onboardingGate = readSource(
    "components",
    "layout",
    "useOnboardingGate.js",
  );

  assert.match(onboardingGate, /normalizedRole === "admin"/);
  assert.match(onboardingGate, /profileMode === "onboarding"/);
  assert.match(
    onboardingGate,
    /navigate\("\/admin\/getting-started", \{ replace: true \}\)/,
  );
});

test("tenant admin guide exits always leave the full-screen setup shell", () => {
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  const adminRoutes = readSource("routes", "adminRoutes.jsx");
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(setupRoute, /label === "finish later"/);
  assert.match(setupRoute, /label === "complete setup"/);
  assert.match(setupRoute, /label === "back to dashboard"/);
  assert.match(setupRoute, /await guide\.finish\(\)/);
  assert.match(setupRoute, /leaveAdminSetup\("\/admin\/dashboard"\)/);
  assert.match(roleGuide, /!hasGuideExitSuppression\(role\)/);
  assert.match(
    adminRoutes,
    /path="\/admin\/getting-started" element=\{<AdminGettingStartedRoute \/>\}/,
  );
});

test("other actor guide exits return to the configured dashboard", () => {
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");

  assert.match(roleGuide, /navigate\(guide\.config\.dashboardRoute, \{ replace: true \}\)/);
  assert.match(roleGuide, /onClick=\{\(\) => navigate\(guide\.config\.dashboardRoute\)\}/);
});

test("terminal guide completion must be confirmed before leaving setup", () => {
  const guideService = readSource("services", "guideService.js");
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");

  assert.match(guideService, /const terminalWrite = TERMINAL_STATUSES\.has\(requestedStatus\)/);
  assert.match(guideService, /ensureTerminalConfirmation\(requestedStatus, response\)/);
  assert.match(guideService, /throw error;/);
  assert.doesNotMatch(setupRoute, /finally\s*\{\s*leaveAdminSetup/);
  assert.match(
    setupRoute,
    /await guide\.finish\(\);\s*leaveAdminSetup\("\/admin\/dashboard"\)/,
  );
});

test("teacher and parent guide fallback state is account-global while student and admin stay tenant-scoped", () => {
  const guideService = readSource("services", "guideService.js");

  assert.match(guideService, /"teacher_account"/);
  assert.match(guideService, /"parent_account"/);
  assert.match(guideService, /const tenant = accountScoped\s*\? "global"/);
  assert.match(guideService, /user\.tenant_id/);
});

test("a failed guide-state read cannot auto-classify a user as a fresh guide", () => {
  const guideService = readSource("services", "guideService.js");
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(
    guideService,
    /catch \{\s*return persistFallback\(guideKey, \{\s*\.\.\.localState,\s*sync_pending: true,/,
  );
  assert.match(roleGuide, /!syncPending/);
});
