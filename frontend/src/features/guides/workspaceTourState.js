export const TOUR_REQUEST_EVENT = "weave:request-workspace-tour";
export const TOUR_QUEUED_EVENT = "weave:workspace-tour-queued";
export const TOUR_STATE_CHANGED_EVENT = "weave:workspace-tour-state-changed";
export const TOUR_QUEUED_STEP = "welcome_pending";
export const TOUR_SEEN_STEP = "welcome_seen";
export const TOUR_PAUSED_PREFIX = "paused:";

export const tourKeyForRole = (role) =>
  ["admin", "teacher", "student", "parent"].includes(role)
    ? `${role}_sidebar_welcome`
    : null;

export const pausedTourStep = (index = -1) => {
  const parsed = Number(index);
  return `${TOUR_PAUSED_PREFIX}${Number.isInteger(parsed) ? Math.max(-1, parsed) : -1}`;
};

export const isPausedTourState = (state) =>
  state?.status === "in_progress" &&
  String(state?.current_step || "").startsWith(TOUR_PAUSED_PREFIX);

export const resumeIndexFromState = (state) => {
  const value = String(state?.current_step || "");
  if (!value.startsWith(TOUR_PAUSED_PREFIX)) return -1;
  const parsed = Number(value.slice(TOUR_PAUSED_PREFIX.length));
  return Number.isInteger(parsed) ? Math.max(-1, parsed) : -1;
};

// Missing history is not evidence of a new account. Automatic tours are only
// shown after an explicit first-workspace boundary has queued them.
export const canAutoShowTour = (state) =>
  state?.status === "in_progress" &&
  state?.current_step === TOUR_QUEUED_STEP &&
  state?.sync_pending === false;

export const isTourIncomplete = (state) => state?.status === "in_progress";

export function publishTourState(role, state) {
  if (typeof window === "undefined" || !tourKeyForRole(role)) return;
  window.dispatchEvent(
    new CustomEvent(TOUR_STATE_CHANGED_EVENT, {
      detail: { role, state },
    }),
  );
}

export async function queueInitialTour(role, shouldQueue, service) {
  const key = tourKeyForRole(role);
  if (!shouldQueue || !key || !service) return false;

  const state = await service.getState(key);
  if (state.status !== "not_started" || state.sync_pending) return false;

  const saved = await service.updateState(key, {
    status: "in_progress",
    current_step: TOUR_QUEUED_STEP,
    remind_after: null,
  });
  const queued = canAutoShowTour(saved);

  if (queued && typeof window !== "undefined") {
    publishTourState(role, saved);
    window.dispatchEvent(
      new CustomEvent(TOUR_QUEUED_EVENT, { detail: { role, state: saved } }),
    );
  }

  return queued;
}

export function requestWorkspaceTour(role, { resume = false } = {}) {
  if (typeof window === "undefined" || !tourKeyForRole(role)) return;
  window.dispatchEvent(
    new CustomEvent(TOUR_REQUEST_EVENT, { detail: { role, resume } }),
  );
}
