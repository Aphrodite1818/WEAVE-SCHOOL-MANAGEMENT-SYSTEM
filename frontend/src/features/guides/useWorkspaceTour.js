import { useEffect, useRef, useState } from "react";
import { guideService } from "../../services/guideService";
import { canAutoShowTour, TOUR_REQUEST_EVENT, tourKeyForRole } from "./workspaceTourState";

export default function useWorkspaceTour({ role, enabled, pathname, navigationKey }) {
  const [open, setOpen] = useState(false);
  const [automatic, setAutomatic] = useState(false);
  const claimed = useRef(false);
  const key = tourKeyForRole(role);

  useEffect(() => {
    if (!enabled || !key || pathname !== `/${role}/dashboard`) return undefined;
    let cancelled = false;
    async function checkWelcome() {
      const state = await guideService.getState(key);
      if (cancelled || claimed.current || !canAutoShowTour(state)) return;
      claimed.current = true;
      // Consume the automatic invitation before showing it. A reload or a
      // school switch must not interrupt an established user with another tour.
      const saved = await guideService.updateState(key, {
        status: "in_progress", current_step: "welcome_seen", remind_after: null,
      });
      if (!cancelled && !saved.sync_pending) {
        setAutomatic(true);
        setOpen(true);
      }
    }
    checkWelcome();
    return () => { cancelled = true; };
  }, [enabled, key, pathname, role, navigationKey]);

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

  const close = async (completed) => {
    if (automatic) {
      await guideService.updateState(key, {
        status: completed ? "completed" : "dismissed",
        current_step: null, remind_after: null,
      });
    }
    setOpen(false);
  };
  return { open: open && enabled, close };
}
