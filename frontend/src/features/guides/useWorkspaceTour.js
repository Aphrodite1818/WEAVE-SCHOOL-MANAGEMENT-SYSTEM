import { useCallback, useEffect, useRef, useState } from "react";
import { guideService } from "../../services/guideService";
import {
  canAutoShowTour,
  TOUR_QUEUED_EVENT,
  TOUR_REQUEST_EVENT,
  tourKeyForRole,
} from "./workspaceTourState";

export default function useWorkspaceTour({ role, enabled, pathname, navigationKey }) {
  const [open, setOpen] = useState(false);
  const [automatic, setAutomatic] = useState(false);
  const [queueVersion, setQueueVersion] = useState(0);
  const claimed = useRef(false);
  const key = tourKeyForRole(role);

  const checkWelcome = useCallback(async () => {
    if (!enabled || !key || pathname !== `/${role}/dashboard` || claimed.current) {
      return;
    }

    let state = await guideService.getState(key);
    if (state?.sync_pending && typeof navigator !== "undefined" && navigator.onLine) {
      state = await guideService.retryPendingState(key);
    }
    if (!canAutoShowTour(state) || claimed.current) return;

    claimed.current = true;
    const saved = await guideService.updateState(key, {
      status: "in_progress",
      current_step: "welcome_seen",
      remind_after: null,
    });
    if (!saved.sync_pending) {
      setAutomatic(true);
      setOpen(true);
    } else {
      // The invitation was not durably consumed. Allow a later online/dashboard
      // retry instead of permanently suppressing the first tour in this mount.
      claimed.current = false;
    }
  }, [enabled, key, pathname, role]);

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
    const replay = (event) => {
      if (!enabled || !key || event.detail?.role !== role) return;
      claimed.current = true;
      setAutomatic(false);
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
    setAutomatic(false);
  }, [key]);

  const close = async (completed) => {
    if (automatic) {
      await guideService.updateState(key, {
        status: completed ? "completed" : "dismissed",
        current_step: null,
        remind_after: null,
      });
    }
    setOpen(false);
  };

  return { open: open && enabled, close };
}
