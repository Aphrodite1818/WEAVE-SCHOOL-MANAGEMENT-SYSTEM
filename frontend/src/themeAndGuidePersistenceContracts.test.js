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
  assert.match(roleGuide, /window\.addEventListener\("online", retryPendingState\)/);
});

test("role guides follow runtime attendance exposure", () => {
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(roleGuide, /useRuntimeConfig/);
  assert.match(
    roleGuide,
    /runtimeConfig\?\.features\?\.attendance !== false/,
  );
  assert.match(
    roleGuide,
    /baseConfig\.steps[\s\S]*\.filter\(\(step\) => step\.id !== "attendance"\)/,
  );
  assert.match(roleGuide, /ATTENDANCE_HIDDEN_DESCRIPTIONS/);
  assert.match(roleGuide, /ATTENDANCE_HIDDEN_STEP_DESCRIPTIONS/);
  assert.match(roleGuide, /before entering scores/);
  assert.match(roleGuide, /const storedIndex = baseConfig\.steps\.findIndex/);
  assert.match(roleGuide, /baseIndex < storedIndex/);
});
