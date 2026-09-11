import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("school setup readiness cannot disable a freshly queued workspace tour", () => {
  const dashboardLayout = readSource("components", "layout", "DashboardLayout.jsx");
  const tourStart = dashboardLayout.indexOf("const tour = useWorkspaceTour({");
  const tourEnd = dashboardLayout.indexOf("const showGettingStartedBanner", tourStart);
  const tourBlock = dashboardLayout.slice(tourStart, tourEnd);

  assert.ok(tourStart >= 0 && tourEnd > tourStart);
  assert.doesNotMatch(tourBlock, /schoolSetup\.loading/);
  assert.doesNotMatch(tourBlock, /setupEnabled/);

  const bannerStart = dashboardLayout.indexOf("const showGettingStartedBanner");
  const bannerEnd = dashboardLayout.indexOf("const showWorkspaceTourReminder", bannerStart);
  const bannerBlock = dashboardLayout.slice(bannerStart, bannerEnd);

  assert.match(bannerBlock, /!schoolSetup\.loading/);
  assert.match(bannerBlock, /!tour\.open/);
});
