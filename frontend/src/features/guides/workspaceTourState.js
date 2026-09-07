export const TOUR_REQUEST_EVENT = "weave:request-workspace-tour";
export const TOUR_QUEUED_STEP = "welcome_pending";
export const tourKeyForRole = (role) =>
  ["admin", "teacher", "student", "parent"].includes(role)
    ? `${role}_sidebar_welcome`
    : null;

// Missing history is not evidence of a new account. Only initial profile
// onboarding queues a welcome; manual replays never reset persisted history.
export const canAutoShowTour = (state) =>
  state?.status === "in_progress" &&
  state?.current_step === TOUR_QUEUED_STEP &&
  state?.sync_pending === false;

export async function queueInitialTour(role, completedInitialOnboarding, service) {
  const key = tourKeyForRole(role);
  if (!completedInitialOnboarding || !key) return;
  const state = await service.getState(key);
  if (state.status === "not_started" && !state.sync_pending) {
    await service.updateState(key, {
      status: "in_progress", current_step: TOUR_QUEUED_STEP, remind_after: null,
    });
  }
}

export function requestWorkspaceTour(role) {
  window.dispatchEvent(new CustomEvent(TOUR_REQUEST_EVENT, { detail: { role } }));
}
