import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  canAutoShowTour,
  queueInitialTour,
  TOUR_QUEUED_STEP,
} from "./workspaceTourState.js";

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("explicit first-workspace eligibility is persisted only from a fresh guide", async () => {
  const updates = [];
  const service = {
    getState: async () => ({ status: "not_started", sync_pending: false }),
    updateState: async (_key, payload) => {
      updates.push(payload);
      return { ...payload, sync_pending: false };
    },
  };

  const queued = await queueInitialTour("admin", true, service);
  assert.equal(queued, true);
  assert.deepEqual(updates, [
    {
      status: "in_progress",
      current_step: TOUR_QUEUED_STEP,
      remind_after: null,
    },
  ]);
});

test("completed or dismissed users are never automatically requeued", async () => {
  for (const status of ["completed", "dismissed"]) {
    let writes = 0;
    const service = {
      getState: async () => ({ status, sync_pending: false }),
      updateState: async () => {
        writes += 1;
        return {};
      },
    };
    assert.equal(await queueInitialTour("teacher", true, service), false);
    assert.equal(writes, 0);
  }
});

test("admin setup completion can recover a non-terminal premature welcome state", async () => {
  const updates = [];
  const service = {
    getState: async () => ({
      status: "in_progress",
      current_step: "welcome_seen",
      sync_pending: false,
    }),
    updateState: async (_key, payload) => {
      updates.push(payload);
      return { ...payload, sync_pending: false };
    },
  };

  const queued = await queueInitialTour("admin", true, service, {
    requeueNonTerminal: true,
  });
  assert.equal(queued, true);
  assert.deepEqual(updates, [
    {
      status: "in_progress",
      current_step: TOUR_QUEUED_STEP,
      remind_after: null,
    },
  ]);
});

test("admin setup completion does not reopen terminal workspace tours", async () => {
  for (const status of ["completed", "dismissed"]) {
    let writes = 0;
    const service = {
      getState: async () => ({ status, sync_pending: false }),
      updateState: async () => {
        writes += 1;
        return {};
      },
    };
    assert.equal(
      await queueInitialTour("admin", true, service, {
        requeueNonTerminal: true,
      }),
      false,
    );
    assert.equal(writes, 0);
  }
});

test("only a durably queued welcome is eligible for automatic display", () => {
  assert.equal(
    canAutoShowTour({
      status: "in_progress",
      current_step: TOUR_QUEUED_STEP,
      sync_pending: false,
    }),
    true,
  );
  assert.equal(
    canAutoShowTour({
      status: "in_progress",
      current_step: TOUR_QUEUED_STEP,
      sync_pending: true,
    }),
    false,
  );
  assert.equal(canAutoShowTour({ status: "not_started", sync_pending: false }), false);
});

test("all first-entry actor boundaries queue or consume the workspace tour", () => {
  const onboardingGate = readSource("components", "layout", "useOnboardingGate.js");
  const adminGettingStartedRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  const invitation = readSource("pages", "public", "InvitationAcceptancePage.jsx");
  const studentPassword = readSource("pages", "student", "StudentChangePasswordPage.jsx");
  const tourHook = readSource("features", "guides", "useWorkspaceTour.js");
  const teacherRoutes = readSource("routes", "teacherRoutes.jsx");
  const parentRoutes = readSource("routes", "parentRoutes.jsx");

  assert.match(onboardingGate, /completedInitialOnboarding && normalizedRole !== "admin"/);
  assert.match(adminGettingStartedRoute, /queueInitialTour\("admin", true, guideService, \{\s*requeueNonTerminal: true,/);
  assert.match(invitation, /queueInitialTour\(role, true, guideService\)/);
  assert.match(studentPassword, /queueInitialTour\("student", true, guideService\)/);
  assert.match(tourHook, /pathname !== `\/\$\{role\}\/dashboard`/);
  assert.match(tourHook, /TOUR_QUEUED_EVENT/);
  assert.doesNotMatch(teacherRoutes, /\/teacher\/schools[\s\S]{0,180}onboardingModalEnabled=\{false\}/);
  assert.doesNotMatch(parentRoutes, /\/parent\/schools[\s\S]{0,180}onboardingModalEnabled=\{false\}/);
});

test("superadmin never receives a workspace tour key", () => {
  assert.equal(canAutoShowTour(null), false);
  const source = readSource("features", "guides", "workspaceTourState.js");
  assert.doesNotMatch(source, /\["admin", "teacher", "student", "parent", "superadmin"\]/);
});
