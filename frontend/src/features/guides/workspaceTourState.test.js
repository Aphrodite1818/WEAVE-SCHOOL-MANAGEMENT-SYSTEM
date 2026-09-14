import assert from "node:assert/strict";
import test from "node:test";

import {
  canAutoShowTour,
  isPausedTourState,
  pausedTourStep,
  queueInitialTour,
  resumeIndexFromState,
  TOUR_QUEUED_STEP,
} from "./workspaceTourState.js";

test("paused tour state preserves resume position and remains incomplete", () => {
  const state = {
    status: "in_progress",
    current_step: pausedTourStep(3),
    sync_pending: false,
  };

  assert.equal(isPausedTourState(state), true);
  assert.equal(resumeIndexFromState(state), 3);
  assert.equal(canAutoShowTour(state), false);
});

test("welcome queued state auto-opens only once before it becomes paused", () => {
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
      status: "dismissed",
      current_step: null,
      sync_pending: false,
    }),
    false,
  );
  assert.equal(
    canAutoShowTour({
      status: "completed",
      current_step: null,
      sync_pending: false,
    }),
    false,
  );
});

test("dismissed and completed tours cannot be requeued as first-workspace tours", async () => {
  for (const status of ["dismissed", "completed"]) {
    let updates = 0;
    const service = {
      getState: async () => ({ status, sync_pending: false }),
      updateState: async () => {
        updates += 1;
        return null;
      },
    };

    const queued = await queueInitialTour("teacher", true, service);
    assert.equal(queued, false);
    assert.equal(updates, 0);
  }
});

test("new first-workspace eligibility persists an explicit queued state", async () => {
  let payload = null;
  const service = {
    getState: async () => ({ status: "not_started", sync_pending: false }),
    updateState: async (_key, nextPayload) => {
      payload = nextPayload;
      return {
        ...nextPayload,
        sync_pending: false,
      };
    },
  };

  const queued = await queueInitialTour("parent", true, service);
  assert.equal(queued, true);
  assert.deepEqual(payload, {
    status: "in_progress",
    current_step: TOUR_QUEUED_STEP,
    remind_after: null,
  });
});
