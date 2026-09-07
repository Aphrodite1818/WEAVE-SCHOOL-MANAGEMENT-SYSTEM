import assert from "node:assert/strict";
import test from "node:test";

import { ROLE_GUIDES, guideForRole } from "./roleGuideConfig.js";

const expectedRoles = ["admin", "teacher", "parent", "student"];
const expectedStepCounts = {
  admin: 4,
  teacher: 4,
  parent: 4,
  student: 4,
};

test("every supported dashboard role has a valid page guide", () => {
  assert.deepEqual(Object.keys(ROLE_GUIDES).sort(), [...expectedRoles].sort());

  for (const role of expectedRoles) {
    const guide = guideForRole(role);
    assert.ok(guide);
    assert.match(guide.key, /^[a-z0-9][a-z0-9_-]+$/);
    assert.equal(guide.route, `/${role}/getting-started`);
    assert.equal(guide.dashboardRoute, `/${role}/dashboard`);

    const expectedStepCount = expectedStepCounts[role];
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

test("admin setup contains the four guided school-year milestones", () => {
  assert.deepEqual(
    ROLE_GUIDES.admin.steps.map((step) => step.id),
    ["session", "term", "calendar", "start_term"],
  );
  assert.equal(ROLE_GUIDES.admin.key, "tenant_admin_academic_setup_v2");
  assert.ok(ROLE_GUIDES.admin.steps.every((step) => !step.optional && !step.feature));
});

test("teacher guide exposes class-teacher comments without score-entry authority", () => {
  assert.deepEqual(
    ROLE_GUIDES.teacher.steps.map((step) => step.id),
    ["classes", "comments", "attendance", "calendar"],
  );
  assert.equal(ROLE_GUIDES.teacher.steps[1].to, "/teacher/student-comments");
});
