export const TOUR_REQUEST_EVENT = "weave:request-workspace-tour";
export const TOUR_QUEUED_EVENT = "weave:workspace-tour-queued";
export const TOUR_QUEUED_STEP = "welcome_pending";

export const tourKeyForRole = (role) =>
  ["admin", "teacher", "student", "parent"].includes(role)
    ? `${role}_sidebar_welcome`
    : null;

// Missing history is not evidence of a new account. Automatic tours are only
// shown after an explicit first-workspace boundary has queued them.
export const canAutoShowTour = (state) =>
  state?.status === "in_progress" &&
  state?.current_step === TOUR_QUEUED_STEP &&
  state?.sync_pending === false;

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
    window.dispatchEvent(
      new CustomEvent(TOUR_QUEUED_EVENT, { detail: { role } }),
    );
  }

  return queued;
}

export function requestWorkspaceTour(role) {
  window.dispatchEvent(new CustomEvent(TOUR_REQUEST_EVENT, { detail: { role } }));
}
