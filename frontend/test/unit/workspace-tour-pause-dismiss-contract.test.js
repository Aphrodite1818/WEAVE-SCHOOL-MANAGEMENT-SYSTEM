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
  new URL("../../src/components/guides/WorkspaceTourResumeBanner.jsx", import.meta.url),
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
  assert.match(
    tourSource,
    /finish\("paused", role === "admin"\)/,
  );
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
