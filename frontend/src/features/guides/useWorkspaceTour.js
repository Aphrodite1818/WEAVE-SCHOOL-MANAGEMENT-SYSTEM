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
  TEACHER_CLASS_DUTIES_GUIDE_KEY,
  TEACHER_CLASS_DUTY_ROUTES,
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
  hasClassTeacherDuties = false,
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
  const [classDutyTour, setClassDutyTour] = useState(false);
  const [focusRoutes, setFocusRoutes] = useState(null);
  const [upgradeQueue, setUpgradeQueue] = useState(null);
  const claimed = useRef(false);
  const queuedWelcomeRef = useRef(null);
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
    queuedWelcomeRef.current = null;
    setOpen(false);
    setResumeIndex(-1);
    setFocusTo(null);
    setPendingRequest(null);
    setDedicated(false);
    setClassDutyTour(false);
    setFocusRoutes(null);
    setUpgradeQueue(null);
    setState(null);
  }, [identityKey, key]);

  const presentInitialWelcome = useCallback(
    async (nextState) => {
      if (!canAutoShowTour(nextState) || claimed.current) return false;

      claimed.current = true;
      queuedWelcomeRef.current = null;
      setInitialWelcome(true);
      setResumeIndex(-1);
      setOpen(true);

      // Claim the already-confirmed welcome before persisting its resumable
      // state. This keeps the live onboarding handoff deterministic even if a
      // concurrent guide read is stale or deduplicated.
      await saveState({
        status: "in_progress",
        current_step: pausedTourStep(-1),
        remind_after: null,
      });
      return true;
    },
    [saveState],
  );

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
    if (await presentInitialWelcome(nextState)) return;

    if (
      role !== "teacher" ||
      !hasClassTeacherDuties ||
      nextState?.status === "in_progress" ||
      claimed.current
    ) {
      return;
    }
    const dutyState = await guideService.getState(
      TEACHER_CLASS_DUTIES_GUIDE_KEY,
    );
    if (!canAutoShowTour(dutyState) || claimed.current) return;

    claimed.current = true;
    setInitialWelcome(false);
    setClassDutyTour(true);
    setDedicated(true);
    setFocusRoutes(TEACHER_CLASS_DUTY_ROUTES);
    setResumeIndex(0);
    setOpen(true);

    // Class-duty guides are dedicated one-shot announcements. Open first so a
    // slow or failed state write cannot suppress the UI that earned the claim.
    await guideService.updateState(TEACHER_CLASS_DUTIES_GUIDE_KEY, {
      status: "in_progress",
      current_step: TOUR_SEEN_STEP,
      remind_after: null,
    });
  }, [
    enabled,
    hasClassTeacherDuties,
    key,
    pathname,
    presentInitialWelcome,
    refreshState,
    role,
  ]);

  useEffect(() => {
    if (!enabled || role !== "admin" || !pathname.startsWith("/admin/")) return;
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
    const queued = (event) => {
      if (!key || event.detail?.role !== role) return;
      const queuedState = event.detail?.state || null;
      queuedWelcomeRef.current = canAutoShowTour(queuedState)
        ? queuedState
        : null;
      if (queuedState) setState(queuedState);
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
    if (
      !enabled ||
      !key ||
      pathname !== `/${role}/dashboard` ||
      claimed.current
    ) {
      return;
    }

    const queuedState = queuedWelcomeRef.current;
    if (!canAutoShowTour(queuedState)) return;

    let cancelled = false;
    Promise.resolve(presentInitialWelcome(queuedState)).catch(() => {
      if (!cancelled) claimed.current = false;
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, key, pathname, presentInitialWelcome, queueVersion, role]);

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
      if (classDutyTour) {
        await guideService.updateState(TEACHER_CLASS_DUTIES_GUIDE_KEY, {
          status: outcome === "completed" ? "completed" : "dismissed",
          current_step: null,
          remind_after: null,
        });
        setOpen(false);
        setResumeIndex(-1);
        setFocusTo(null);
        setFocusRoutes(null);
        setDedicated(false);
        setClassDutyTour(false);
        return;
      }
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

    if (
      role === "teacher" &&
      hasClassTeacherDuties &&
      ["completed", "dismissed"].includes(outcome)
    ) {
      const dutyState = await guideService.getState(
        TEACHER_CLASS_DUTIES_GUIDE_KEY,
      );
      if (dutyState?.status === "in_progress") {
        await guideService.updateState(TEACHER_CLASS_DUTIES_GUIDE_KEY, {
          status: "completed",
          current_step: null,
          remind_after: null,
        });
      }
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
    focusRoutes,
    dedicated,
    classDutyTour,
    state,
    refreshState,
    incomplete: state?.status === "in_progress",
    dismissed: state?.status === "dismissed",
    completed: state?.status === "completed",
  };
}
