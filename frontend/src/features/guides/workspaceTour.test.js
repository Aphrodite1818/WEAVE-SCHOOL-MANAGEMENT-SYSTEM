import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { canAutoShowTour, queueInitialTour, TOUR_QUEUED_STEP, tourKeyForRole } from "./workspaceTourState.js";
import { schoolYearProgress } from "./schoolYearProgress.js";
import { tourContentForItem } from "./workspaceTourContent.js";

const empty = { status: "not_started", current_step: null, sync_pending: false };
const fakeService = (initial = empty) => {
  let state = { ...initial };
  const writes = [];
  return { writes, getState: async () => state, updateState: async (key, payload) => {
    writes.push({ key, payload });
    state = { ...state, ...payload };
    return state;
  } };
};

test("missing or legacy guide history never auto-opens a tour", () => {
  for (const state of [null, undefined, empty, { ...empty, status: "completed" }, { ...empty, status: "dismissed" }, { ...empty, status: "in_progress", current_step: "classes" }]) {
    assert.equal(canAutoShowTour(state), false);
  }
});

test("only a confirmed initial-onboarding invitation can auto-open", () => {
  const queued = { ...empty, status: "in_progress", current_step: TOUR_QUEUED_STEP };
  assert.equal(canAutoShowTour(queued), true);
  assert.equal(canAutoShowTour({ ...queued, sync_pending: true }), false);
  assert.equal(canAutoShowTour({ ...queued, sync_pending: undefined }), false);
  for (const status of ["completed", "dismissed"]) assert.equal(canAutoShowTour({ ...queued, status }), false);
  assert.equal(canAutoShowTour({ ...queued, current_step: "welcome_seen" }), false);
});

test("all four initial profile completions queue one invitation, with superadmin excluded", async () => {
  for (const role of ["admin", "teacher", "student", "parent"]) {
    const service = fakeService();
    await queueInitialTour(role, true, service);
    await queueInitialTour(role, true, service);
    assert.equal(service.writes.length, 1);
    assert.equal(service.writes[0].key, tourKeyForRole(role));
    assert.equal(canAutoShowTour(await service.getState()), true);
  }
  const service = fakeService();
  await queueInitialTour("superadmin", true, service);
  assert.equal(tourKeyForRole("superadmin"), null);
  assert.equal(service.writes.length, 0);
});

test("profile edits, returning users and failed reads never enrol in a tour", async () => {
  const service = fakeService();
  await queueInitialTour("student", false, service);
  assert.equal(service.writes.length, 0);
  for (const status of ["completed", "dismissed", "in_progress"]) {
    const returning = fakeService({ ...empty, status });
    await queueInitialTour("teacher", true, returning);
    assert.equal(returning.writes.length, 0);
  }
  const offline = fakeService({ ...empty, sync_pending: true });
  await queueInitialTour("parent", true, offline);
  assert.equal(offline.writes.length, 0);
});

test("school year progress counts guided milestones, not unrelated entities or visits", () => {
  let progress = schoolYearProgress({ subjects: true, students: true, readiness: true });
  assert.equal(progress.completedCount, 0);
  assert.equal(progress.nextStep, "session");
  assert.equal(progress.canOpen("session"), true);
  assert.equal(progress.canOpen("term"), false);
  assert.equal(progress.canOpen("calendar"), false);
  assert.equal(progress.canOpen("start_term"), false);

  progress = schoolYearProgress({ session: true, term: true, calendar: false, start_term: false });
  assert.equal(progress.completedCount, 2);
  assert.equal(progress.nextStep, "calendar");
  assert.equal(progress.canOpen("calendar"), true);
  assert.equal(progress.complete, false);

  progress = schoolYearProgress({ session: true, term: true, calendar: true, start_term: false });
  assert.equal(progress.completedCount, 3);
  assert.equal(progress.completedStages, 2);
  assert.equal(progress.nextStep, null);
  assert.equal(progress.canOpen("start_term"), false);
  assert.equal(progress.complete, true);

  progress = schoolYearProgress({ session: true, term: true, calendar: true, start_term: true });
  assert.equal(progress.completedCount, 3);
  assert.equal(progress.completedStages, 2);
  assert.equal(progress.nextStep, null);
  assert.equal(progress.complete, true);
  assert.equal(schoolYearProgress({ session: "true", term: null }).completedCount, 0);
});

test("tour copy covers every sidebar destination for all four roles", () => {
  const source = readFileSync(new URL("../../components/layout/navConfig.js", import.meta.url), "utf8");
  const items = [...source.matchAll(/label: "([^"]+)",\s*to: "([^"]+)"/g)];
  for (const role of ["admin", "teacher", "student", "parent"]) {
    const matching = items.filter(([, , to]) => to.startsWith(`/${role}/`));
    assert.ok(matching.length > 5);
    for (const [, label, to] of matching) {
      const content = tourContentForItem(role, { label, to });
      assert.equal(content.label, label);
      assert.equal(content.to, to);
      assert.equal(content.preview.length, 3);
      assert.ok(content.description.length > 30);
      if (!to.endsWith("/dashboard")) assert.notEqual(content.title, "Your everyday starting point", to);
    }
  }
});

test("dedicated upgrade tours explain newly unlocked plan features", () => {
  const imports = tourContentForItem(
    "admin",
    { label: "Imports", to: "/admin/imports" },
    { dedicated: true },
  );
  const cbt = tourContentForItem(
    "admin",
    { label: "CBT Servers", to: "/admin/cbt" },
    { dedicated: true },
  );
  const branding = tourContentForItem(
    "admin",
    { label: "School branding", to: "/admin/settings/branding" },
    { dedicated: true },
  );

  for (const content of [imports, cbt, branding]) {
    assert.match(content.title, /now available/);
    assert.match(content.description, /Your plan now includes/);
    assert.equal(content.preview[0], "New on this plan");
  }
});

test("tour uses visible sidebar targets and restores keyboard access on exit", () => {
  const source = readFileSync(new URL("../../components/guides/WorkspaceTour.jsx", import.meta.url), "utf8");
  assert.match(source, /rendered\.has\(item\.to\)/);
  assert.match(source, /getBoundingClientRect\(\)\.width > 0/);
  assert.match(source, /role="dialog"\s+aria-modal="true"/);
  assert.match(source, /node\.inert = true/);
  assert.match(source, /node\.inert = inert/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /event\.key !== "Tab"/);
  assert.match(source, /previousFocus\.focus/);
});
