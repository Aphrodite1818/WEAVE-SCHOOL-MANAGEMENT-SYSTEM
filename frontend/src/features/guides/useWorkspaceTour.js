import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { authSession } from "../../services/api";
import { guideService } from "../../services/guideService";
import {
  canAutoShowTour,
  consumePendingUpgradeTour,
  pausedTourStep,
  publishTourState,
  resumeIndexFromState,
  TOUR_QUEUED_EVENT,
  TOUR_REQUEST_EVENT,
  TOUR_SEEN_STEP,
  TOUR_STATE_CHANGED_EVENT,
  tourKeyForRole,
} from "./workspaceTourState";

const authIdentityKey = (user) => {
  const actorType = String(
    user?.actor_type || user?.account_type || user?.role || "",
  ).toLowerCase();
  const actorId =
    user?.account_id ||
    user?.tenant_admin_id ||
    user?.teacher_account_id ||
    user?.parent_account_id ||
    user?.actor_id ||
    user?.id ||
    user?.email ||
    "anonymous";
  const tenantId = user?.tenant_id || user?.tenant?.id || "global";
  return `${actorType}:${tenantId}:${actorId}`;
};

export default function useWorkspaceTour({
  role,
  enabled,
  pathname,
  navigationKey,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const currentUser = authSession.getUser() || {};
  const identityKey = authIdentityKey(currentUser);
  const [initialWelcome, setInitialWelcome] = useState(false);
  const [open, setOpen] = useState(false);
  const [resumeIndex, setResumeIndex] = useState(-1);
  const [state, setState] = useState(null);
  const [queueVersion, setQueueVersion] = useState(0);
  const [focusTo, setFocusTo] = useState(null);
  const [pendingRequest, setPendingRequest] = useState(null);
  const [dedicated, setDedicated] = useState(false);
  const [upgradeQueue, setUpgradeQueue] = useState(null);
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

  useEffect(() => {
    claimed.current = false;
    setOpen(false);
    setResumeIndex(-1);
    setFocusTo(null);
    setPendingRequest(null);
    setDedicated(false);
    setUpgradeQueue(null);
    setState(null);
  }, [identityKey, key]);

  const checkWelcome = useCallback(async () => {
    if (
      !enabled ||
      !key ||
      pathname !== `/${role}/dashboard` ||
      claimed.current
    ) {
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
      setInitialWelcome(true);
      setResumeIndex(-1);
      setOpen(true);
    } else {
      claimed.current = false;
    }
  }, [enabled, key, pathname, refreshState, role, saveState]);

  useEffect(() => {
    if (!enabled || role !== "admin" || pathname !== "/admin/dashboard") return;
    const pending = consumePendingUpgradeTour();
    if (
      !pending ||
      (!pending.sidebarTargets?.length && !pending.settingsTarget)
    )
      return;
    setUpgradeQueue(pending);
    setInitialWelcome(false);
    setFocusTo(pending.sidebarTargets?.[0] || null);
    setDedicated(true);
    setResumeIndex(0);
    setOpen(true);
  }, [enabled, pathname, role]);

  useEffect(() => {
    let cancelled = false;
    Promise.resolve(checkWelcome()).catch(() => {
      if (!cancelled) claimed.current = false;
    });
    return () => {
      cancelled = true;
    };
  }, [checkWelcome, identityKey, navigationKey, queueVersion]);

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
    if (!pendingRequest || pendingRequest.destination !== location.pathname)
      return;
    setPendingRequest(null);
    setFocusTo(pendingRequest.focusTo || null);
    setDedicated(Boolean(pendingRequest.dedicated));
    setInitialWelcome(false);
    setResumeIndex(pendingRequest.dedicated ? 0 : -1);
    setOpen(true);
  }, [location.pathname, pendingRequest]);

  useEffect(() => {
    const replay = async (event) => {
      if (!enabled || !key || event.detail?.role !== role) return;
      claimed.current = true;
      if (event.detail?.destination && event.detail.destination !== pathname) {
        setPendingRequest(event.detail);
        navigate(event.detail.destination, { replace: true });
        return;
      }
      setInitialWelcome(false);
      setFocusTo(event.detail?.focusTo || null);
      setDedicated(Boolean(event.detail?.dedicated));
      let nextState = null;
      if (event.detail?.resume) {
        nextState = await refreshState();
      }
      setResumeIndex(
        event.detail?.dedicated
          ? 0
          : event.detail?.resume
            ? resumeIndexFromState(nextState)
            : -1,
      );
      setOpen(true);
    };
    window.addEventListener(TOUR_REQUEST_EVENT, replay);
    return () => window.removeEventListener(TOUR_REQUEST_EVENT, replay);
  }, [enabled, key, navigate, pathname, refreshState, role]);

  const close = async ({ outcome = "paused", index = -1 } = {}) => {
    if (!key) {
      setOpen(false);
      return;
    }

    if (dedicated) {
      if (upgradeQueue?.sidebarTargets?.length > 1) {
        const [, ...remaining] = upgradeQueue.sidebarTargets;
        setUpgradeQueue({ ...upgradeQueue, sidebarTargets: remaining });
        setFocusTo(remaining[0]);
        setResumeIndex(-1);
        setOpen(true);
        return;
      }
      if (upgradeQueue?.settingsRoute && upgradeQueue.settingsTarget) {
        navigate(upgradeQueue.settingsRoute, { replace: true });
        setUpgradeQueue({
          ...upgradeQueue,
          sidebarTargets: [],
          settingsRoute: null,
        });
        setFocusTo(upgradeQueue.settingsTarget);
        setResumeIndex(-1);
        setOpen(true);
        return;
      }
      setOpen(false);
      setResumeIndex(-1);
      setFocusTo(null);
      setDedicated(false);
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
    initialWelcome,
    close,
    resumeIndex,
    focusTo,
    dedicated,
    state,
    refreshState,
    incomplete: state?.status === "in_progress",
    dismissed: state?.status === "dismissed",
    completed: state?.status === "completed",
  };
}
