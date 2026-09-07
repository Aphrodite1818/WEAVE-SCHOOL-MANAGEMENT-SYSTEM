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
  TOUR_STATE_CHANGED_EVENT,
  tourKeyForRole,
} from "./workspaceTourState";

export default function useWorkspaceTour({ role, enabled, pathname, navigationKey }) {
  const [open, setOpen] = useState(false);
  const [resumeIndex, setResumeIndex] = useState(-1);
  const [state, setState] = useState(null);
  const [queueVersion, setQueueVersion] = useState(0);
  const claimed = useRef(false);
  const key = tourKeyForRole(role);

  const acceptState = useCallback(
    (nextState) => {
      setState(nextState || null);
      publishTourState(role, nextState);
      return nextState;
    },
    [role],
  );

  const saveState = useCallback(
    async (payload) => {
      if (!key) return null;
      const saved = await guideService.updateState(key, payload);
      return acceptState(saved);
    },
    [acceptState, key],
  );

  const refreshState = useCallback(async () => {
    if (!enabled || !key) return null;
    let nextState = await guideService.getState(key);
    if (
      nextState?.sync_pending &&
      typeof navigator !== "undefined" &&
      navigator.onLine
    ) {
      nextState = await guideService.retryPendingState(key);
    }
    return acceptState(nextState);
  }, [acceptState, enabled, key]);

  const checkWelcome = useCallback(async () => {
    if (!enabled || !key || pathname !== `/${role}/dashboard` || claimed.current) {
      return;
    }

    const nextState = await refreshState();
    if (!canAutoShowTour(nextState) || claimed.current) return;

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
      claimed.current = false;
    }
  }, [enabled, key, pathname, refreshState, role, saveState]);

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
    if (!enabled || !key) return;
    refreshState().catch(() => {});
  }, [enabled, key, refreshState]);

  useEffect(() => {
    const queued = (event) => {
      if (!key || event.detail?.role !== role) return;
      if (event.detail?.state) setState(event.detail.state);
      setQueueVersion((value) => value + 1);
    };
    const changed = (event) => {
      if (!key || event.detail?.role !== role) return;
      setState(event.detail?.state || null);
    };
    const online = () => setQueueVersion((value) => value + 1);
    window.addEventListener(TOUR_QUEUED_EVENT, queued);
    window.addEventListener(TOUR_STATE_CHANGED_EVENT, changed);
    window.addEventListener("online", online);
    return () => {
      window.removeEventListener(TOUR_QUEUED_EVENT, queued);
      window.removeEventListener(TOUR_STATE_CHANGED_EVENT, changed);
      window.removeEventListener("online", online);
    };
  }, [key, role]);

  useEffect(() => {
    const replay = async (event) => {
      if (!enabled || !key || event.detail?.role !== role) return;
      claimed.current = true;
      let nextState = null;
      if (event.detail?.resume) {
        nextState = await refreshState();
      }
      setResumeIndex(event.detail?.resume ? resumeIndexFromState(nextState) : -1);
      setOpen(true);
    };
    window.addEventListener(TOUR_REQUEST_EVENT, replay);
    return () => window.removeEventListener(TOUR_REQUEST_EVENT, replay);
  }, [enabled, key, refreshState, role]);

  useEffect(() => {
    claimed.current = false;
    setOpen(false);
    setResumeIndex(-1);
    setState(null);
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

  return {
    open: open && enabled,
    close,
    resumeIndex,
    state,
    refreshState,
    incomplete: state?.status === "in_progress",
    dismissed: state?.status === "dismissed",
    completed: state?.status === "completed",
  };
}
