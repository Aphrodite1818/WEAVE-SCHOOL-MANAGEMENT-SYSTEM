import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const tourSource = readFileSync(
  new URL("../../src/components/guides/WorkspaceTour.jsx", import.meta.url),
  "utf8",
);
const shellSource = readFileSync(
  new URL("../../src/components/layout/DashboardLayout.jsx", import.meta.url),
  "utf8",
);
const bannerSource = readFileSync(
  new URL(
    "../../src/components/guides/WorkspaceTourResumeBanner.jsx",
    import.meta.url,
  ),
  "utf8",
);

test("workspace tour distinguishes temporary pause, completion, and explicit dismissal", () => {
  assert.match(tourSource, /finish\("paused"/);
  assert.match(tourSource, /finish\("completed"/);
  assert.match(tourSource, /finish\("dismissed"/);
  assert.match(tourSource, /Don't show this tour again/);
  assert.match(tourSource, /Stop showing the workspace tour\?/);
  assert.match(tourSource, /Skip for now/);
});

test("admin skip-to-setup remains a pause rather than completion", () => {
  assert.match(tourSource, /finish\("paused", Boolean\(onSetup\)\)/);
  assert.match(tourSource, /Skip to school setup/);
});

test("paused workspace tour gets a dashboard resume indicator", () => {
  assert.match(shellSource, /isPausedTourState\(tour\.state\)/);
  assert.match(shellSource, /WorkspaceTourResumeBanner/);
  assert.match(shellSource, /requestWorkspaceTour\(role, \{ resume: true \}\)/);
  assert.match(bannerSource, /Incomplete/);
  assert.match(bannerSource, /Resume tour/);
});

test("dismissed tours are not represented by the incomplete banner", () => {
  assert.match(bannerSource, /state\?\.status !== "in_progress"/);
});

const hookSource = readFileSync(
  new URL("../../src/features/guides/useWorkspaceTour.js", import.meta.url),
  "utf8",
);
const readinessSource = readFileSync(
  new URL(
    "../../src/features/guides/useAdminSetupReadiness.js",
    import.meta.url,
  ),
  "utf8",
);

test("only the initial welcome offers school setup; replay and resume are tour-only", () => {
  assert.match(hookSource, /setInitialWelcome\(true\)/);
  const replay = hookSource.slice(
    hookSource.indexOf("const replay ="),
    hookSource.indexOf("window.addEventListener(TOUR_REQUEST_EVENT"),
  );
  assert.match(replay, /setInitialWelcome\(false\)/);
  assert.match(
    shellSource,
    /onSetup=\{[\s\S]*tour\.initialWelcome && schoolSetupIncomplete/,
  );

  const tourBlock = shellSource.slice(
    shellSource.indexOf("const tour = useWorkspaceTour({"),
    shellSource.indexOf("const showGettingStartedBanner"),
  );
  const setupBannerBlock = shellSource.slice(
    shellSource.indexOf("const showGettingStartedBanner"),
    shellSource.indexOf("const showWorkspaceTourReminder"),
  );
  assert.doesNotMatch(tourBlock, /schoolSetup\.loading|setupEnabled/);
  assert.match(setupBannerBlock, /!schoolSetup\.loading/);
  assert.match(setupBannerBlock, /!tour\.open/);
});

test("finish later leaves a record-based reminder regardless of tour or guide dismissal", () => {
  const bannerCondition = shellSource.slice(
    shellSource.indexOf("const showGettingStartedBanner"),
    shellSource.indexOf("const showWorkspaceTourReminder"),
  );
  assert.match(bannerCondition, /schoolSetupIncomplete/);
  assert.doesNotMatch(bannerCondition, /shouldShowBanner|guideState/);
  assert.match(
    shellSource,
    /schoolYearProgress\(adminSchoolYearCompletion\(schoolSetup\.data\)\)\.complete/,
  );
  assert.doesNotMatch(shellSource, /onDismiss=\{dismissGettingStartedBanner\}/);
  assert.match(readinessSource, /weave:dashboard-cache-invalidated/);
});
