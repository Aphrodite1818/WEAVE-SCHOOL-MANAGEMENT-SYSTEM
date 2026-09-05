import assert from "node:assert/strict";
import test from "node:test";

import { ROLE_GUIDES, guideForRole } from "./roleGuideConfig.js";

const expectedRoles = ["admin", "teacher", "parent", "student"];

test("every supported dashboard role has a valid page guide", () => {
  assert.deepEqual(Object.keys(ROLE_GUIDES).sort(), [...expectedRoles].sort());

  for (const role of expectedRoles) {
    const guide = guideForRole(role);
    assert.ok(guide);
    assert.match(guide.key, /^[a-z0-9][a-z0-9_-]+$/);
    assert.equal(guide.route, `/${role}/getting-started`);
    assert.equal(guide.dashboardRoute, `/${role}/dashboard`);

    const expectedStepCount =
      role === "admin" ? 17 : role === "teacher" ? 3 : 4;
    assert.equal(guide.steps.length, expectedStepCount);
    assert.equal(
      new Set(guide.steps.map((step) => step.id)).size,
      expectedStepCount,
    );

    for (const step of guide.steps) {
      assert.ok(step.label);
      assert.ok(step.description);
      assert.ok(step.icon);
      assert.ok(step.actionLabel);
      assert.ok(step.to.startsWith(`/${role}/`));
    }
  }
});

test("unknown roles do not receive a guide", () => {
  assert.equal(guideForRole("superadmin"), null);
  assert.equal(guideForRole(""), null);
});

test("tenant admin guide follows the academic setup v2 dependency order", () => {
  assert.deepEqual(
    ROLE_GUIDES.admin.steps.map((step) => step.id),
    [
      "school_basics", "session", "term", "calendar", "levels", "arms", "classes",
      "subjects", "curriculum", "departments", "teachers", "assignments", "students",
      "grading", "readiness", "school_logo", "progression",
    ],
  );
});
