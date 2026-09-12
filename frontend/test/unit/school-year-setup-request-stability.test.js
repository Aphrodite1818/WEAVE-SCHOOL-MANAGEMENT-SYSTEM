import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const readSource = (...segments) =>
  fs.readFileSync(path.join(frontendRoot, "src", ...segments), "utf8");

test("school-year setup memoizes derived completion state before passing it to the guide", () => {
  const route = readSource("routes", "AdminGettingStartedRoute.jsx");

  assert.match(route, /import \{ useMemo \} from "react";/);
  assert.match(
    route,
    /const completion = useMemo\(\s*\(\) => adminSchoolYearCompletion\(setup\.data\),\s*\[setup\.data\],\s*\);/,
  );
  assert.match(
    route,
    /completionMap: setup\.loading \|\| setup\.error \? null : completion/,
  );
  assert.doesNotMatch(
    route,
    /const completion = adminSchoolYearCompletion\(setup\.data\);/,
  );
});

test("school-year readiness refresh stays event-driven instead of timer-polled", () => {
  const readinessHook = readSource(
    "features",
    "guides",
    "useAdminSetupReadiness.js",
  );

  assert.match(readinessHook, /refresh\(\);/);
  assert.match(
    readinessHook,
    /window\.addEventListener\("weave:dashboard-cache-invalidated", refresh\)/,
  );
  assert.match(readinessHook, /\[refresh, pathname\]/);
  assert.doesNotMatch(readinessHook, /setInterval\s*\(/);
  assert.doesNotMatch(readinessHook, /setTimeout\s*\(/);
});
