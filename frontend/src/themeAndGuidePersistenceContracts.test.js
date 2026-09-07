import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("browser theme chrome is finalized after branded theme tokens paint", () => {
  const themeSync = readSource("utils", "themeChromeSync.js");
  const brandingProvider = readSource(
    "features",
    "tenant-branding",
    "TenantBrandingProvider.jsx",
  );

  assert.match(themeSync, /paintFrameId/);
  assert.match(
    themeSync,
    /requestAnimationFrame\(\(\) => \{[\s\S]*requestAnimationFrame\(\(\) => \{/,
  );
  assert.match(themeSync, /resolveBackground/);
  assert.match(brandingProvider, /scheduleThemeChromeSync\(\)/);
  assert.match(
    brandingProvider,
    /applyBranding\(scope, branding, currentAppearance\(\)\);[\s\S]*scheduleThemeChromeSync\(\)/,
  );
});

test("tenant admin branding reads reuse the tenant-scoped frontend snapshot", () => {
  const brandingService = readSource("services", "tenantBrandingService.js");

  assert.match(brandingService, /const adminBrandingSnapshots = new Map\(\)/);
  assert.match(brandingService, /const adminBrandingCacheKey/);
  assert.match(brandingService, /getCachedAdminBranding/);
  assert.match(brandingService, /if \(!force\)/);
});

test("failed guide writes remain locally terminal and retryable", () => {
  const guideService = readSource("services", "guideService.js");

  assert.match(guideService, /const PENDING_SUFFIX = ":pending"/);
  assert.match(guideService, /shouldPreserveLocalState/);
  assert.match(guideService, /confirmPendingState/);
  assert.match(guideService, /retryPendingState/);
  assert.match(guideService, /sync_pending: true/);
});

test("stale guide reads cannot trigger a second automatic tutorial", () => {
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(roleGuide, /stateVersionRef = useRef\(0\)/);
  assert.match(roleGuide, /!syncPending/);
  assert.match(
    roleGuide,
    /\["completed", "dismissed"\]\.includes\(guideState\?\.status\)/,
  );
  assert.match(
    roleGuide,
    /window\.addEventListener\("online", retryPendingState\)/,
  );
});

test("workspace tours reset when the authenticated actor changes", () => {
  const workspaceTour = readSource("features", "guides", "useWorkspaceTour.js");
  const resetIndex = workspaceTour.indexOf("[identityKey, key]");
  const welcomeIndex = workspaceTour.indexOf("Promise.resolve(checkWelcome())");

  assert.match(workspaceTour, /authSession\.getUser\(\)/);
  assert.match(workspaceTour, /const authIdentityKey = \(user\) =>/);
  assert.match(workspaceTour, /\}, \[identityKey, key\]\);/);
  assert.match(workspaceTour, /claimed\.current = false/);
  assert.match(workspaceTour, /setUpgradeQueue\(null\)/);
  assert.match(
    workspaceTour,
    /\}, \[checkWelcome, identityKey, navigationKey, queueVersion\]\);/,
  );
  assert.ok(resetIndex >= 0);
  assert.ok(welcomeIndex >= 0);
  assert.ok(resetIndex < welcomeIndex);
});

test("upgrade tutors use feature-tour completion copy", () => {
  const workspaceTour = readSource("components", "guides", "WorkspaceTour.jsx");
  const workspaceTourCss = readSource("components", "guides", "workspaceTour.css");

  assert.match(workspaceTour, /dedicated/);
  assert.match(workspaceTour, /dedicated\s*\?\s*"Done"/);
  assert.match(workspaceTour, /dedicated\s*\?\s*"Close update"/);
  assert.match(workspaceTour, /!\s*dedicated/);
  assert.match(workspaceTour, /tourContentForItem\(role, item, \{ dedicated \}\)/);
  assert.match(workspaceTourCss, /workspace-tour-card-upgrade/);
  assert.match(workspaceTour, /"Go to dashboard"/);
});

test("role guides follow runtime attendance exposure", () => {
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(roleGuide, /useRuntimeConfig/);
  const visibility = readSource("features", "guides", "guideStepVisibility.js");
  assert.match(roleGuide, /runtimeFeatures = runtimeConfig\?\.features/);
  assert.match(roleGuide, /visibleGuideSteps\(baseConfig.steps/);
  assert.match(visibility, /isFeatureAvailable\(step,/);
  assert.match(visibility, /runtimeFeatures,/);
  assert.match(roleGuide, /const storedIndex = baseConfig\.steps\.findIndex/);
  assert.match(roleGuide, /baseIndex < storedIndex/);
});
