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

  assert.match(setupPage, /detail\?\.reason === "resource_limit_reached"/);
  assert.match(setupPage, /actionLabel:\s*"Upgrade plan"/);
  assert.match(
  setupPage,
  /leaveGuideRoute\("admin", "\/admin\/billing\/plans", \{ replace: true \}\)/,
);
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

test("all guided setup exit actions return to the actor dashboard", () => {
  const shell = readSource("components", "layout", "DashboardLayout.jsx");
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");
  const navigation = readSource("features", "guides", "guideNavigation.js");

  assert.match(shell, /onClick=\{finishGuideLater\}/);
  assert.match(adminGuide, /onClick=\{finishLater\}/);
  assert.match(adminGuide, /leaveGuideRoute\("admin", "\/admin\/dashboard"/);
  assert.match(roleGuide, /onClick=\{finishLater\}/);
  assert.match(roleGuide, /leaveGuideRoute\(role, guide\.config\.dashboardRoute/);
  assert.match(navigation, /window\.location\.replace\(destination\)/);
});

test("plan-limit upgrade action leaves setup and opens billing plans", () => {
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");

  assert.match(adminGuide, /onClick=\{goToPlanUpgrade\}/);
  assert.match(
    adminGuide,
    /leaveGuideRoute\("admin", "\/admin\/billing\/plans", \{ replace: true \}\)/,
  );
  assert.doesNotMatch(adminGuide, /warningDialog\.onAction/);
});
