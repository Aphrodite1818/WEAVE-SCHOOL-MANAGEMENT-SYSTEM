import { useCallback, useEffect, useRef, useState } from "react";
import { guideService } from "../../services/guideService";
import {
  canAutoShowTour,
  pausedTourStep,
  publishTourState,
  resumeIndexFromState,
  TOUR_QUEUED_EVENT,
  TOUR_REQUEST_EVENT,
  TOUR_SEEN_STEP,
  tourKeyForRole,
} from "./workspaceTourState";

export default function useWorkspaceTour({ role, enabled, pathname, navigationKey }) {
  const [open, setOpen] = useState(false);
  const [resumeIndex, setResumeIndex] = useState(-1);
  const [queueVersion, setQueueVersion] = useState(0);
  const claimed = useRef(false);
  const key = tourKeyForRole(role);

  const saveState = useCallback(
    async (payload) => {
      if (!key) return null;
      const saved = await guideService.updateState(key, payload);
      publishTourState(role, saved);
      return saved;
    },
    [key, role],
  );

  const checkWelcome = useCallback(async () => {
    if (!enabled || !key || pathname !== `/${role}/dashboard` || claimed.current) {
      return;
    }

    let state = await guideService.getState(key);
    publishTourState(role, state);
    if (state?.sync_pending && typeof navigator !== "undefined" && navigator.onLine) {
      state = await guideService.retryPendingState(key);
      publishTourState(role, state);
    }
    if (!canAutoShowTour(state) || claimed.current) return;

    claimed.current = true;
    const saved = await saveState({
      status: "in_progress",
      current_step: TOUR_SEEN_STEP,
      remind_after: null,
    });
    if (!saved?.sync_pending) {
      setResumeIndex(-1);
      setOpen(true);
    } else {
      // The invitation was not durably consumed. Allow a later online/dashboard
      // retry instead of permanently suppressing the first tour in this mount.
      claimed.current = false;
    }
  }, [enabled, key, pathname, role, saveState]);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve(checkWelcome()).catch(() => {
      if (!cancelled) claimed.current = false;
    });
    return () => {
      cancelled = true;
    };
  }, [checkWelcome, navigationKey, queueVersion]);

  useEffect(() => {
    const queued = (event) => {
      if (!key || event.detail?.role !== role) return;
      setQueueVersion((value) => value + 1);
    };
    const online = () => setQueueVersion((value) => value + 1);
    window.addEventListener(TOUR_QUEUED_EVENT, queued);
    window.addEventListener("online", online);
    return () => {
      window.removeEventListener(TOUR_QUEUED_EVENT, queued);
      window.removeEventListener("online", online);
    };
  }, [key, role]);

  useEffect(() => {
    const replay = async (event) => {
      if (!enabled || !key || event.detail?.role !== role) return;
      claimed.current = true;
      let state = null;
      if (event.detail?.resume) {
        state = await guideService.getState(key);
        publishTourState(role, state);
      }
      setResumeIndex(event.detail?.resume ? resumeIndexFromState(state) : -1);
      setOpen(true);
    };
    window.addEventListener(TOUR_REQUEST_EVENT, replay);
    return () => window.removeEventListener(TOUR_REQUEST_EVENT, replay);
  }, [enabled, key, role]);

  useEffect(() => {
    // Role/account switches remount most shells, but resetting here makes the
    // hook correct even if React preserves the shell instance.
    claimed.current = false;
    setOpen(false);
    setResumeIndex(-1);
  }, [key]);

  const close = async ({ outcome = "paused", index = -1 } = {}) => {
    if (!key) {
      setOpen(false);
      return;
    }

    if (outcome === "completed") {
      await saveState({
        status: "completed",
        current_step: null,
        remind_after: null,
      });
    } else if (outcome === "dismissed") {
      await saveState({
        status: "dismissed",
        current_step: null,
        remind_after: null,
      });
    } else {
      await saveState({
        status: "in_progress",
        current_step: pausedTourStep(index),
        remind_after: null,
      });
    }

    setOpen(false);
    setResumeIndex(-1);
  };

  return { open: open && enabled, close, resumeIndex };
}
