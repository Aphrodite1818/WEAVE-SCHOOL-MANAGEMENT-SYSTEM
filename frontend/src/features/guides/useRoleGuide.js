import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { dashboardService } from "../../services/dashboard.service";
import { guideService } from "../../services/guideService";
import { guideForRole } from "./roleGuideConfig";

const inFuture = (value) => {
  if (!value) return false;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) && timestamp > Date.now();
};

const adminCompletion = (stats = {}) => ({
  foundation: Boolean(stats.active_academic_session && stats.active_academic_term),
  structure:
    Number(stats.total_classes || 0) > 0
    && Number(stats.total_subjects || 0) > 0,
  staff: Number(stats.total_teachers || 0) > 0,
  students: Number(stats.total_students || 0) > 0,
});

export function useRoleGuide({ role, enabled = true }) {
  const navigate = useNavigate();
  const config = guideForRole(role);
  const [guideState, setGuideState] = useState(null);
  const [adminStats, setAdminStats] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(Boolean(config && enabled));

  const completionMap = useMemo(
    () => (role === "admin" ? adminCompletion(adminStats?.stats || {}) : {}),
    [adminStats, role],
  );

  const steps = useMemo(() => {
    if (!config) return [];
    const skipped = new Set(guideState?.skipped_steps || []);
    const storedIndex = Math.max(
      0,
      config.steps.findIndex((step) => step.id === guideState?.current_step),
    );
    return config.steps.map((step, index) => ({
      ...step,
      complete:
        role === "admin"
          ? Boolean(completionMap[step.id])
          : guideState?.status === "completed" || index < storedIndex,
      skipped: skipped.has(step.id),
    }));
  }, [completionMap, config, guideState, role]);

  const firstIncompleteIndex = useMemo(() => {
    const index = steps.findIndex((step) => !step.complete && !step.skipped);
    return index === -1 ? Math.max(steps.length - 1, 0) : index;
  }, [steps]);

  const currentIndex = useMemo(() => {
    if (!steps.length) return 0;
    const stored = steps.findIndex((step) => step.id === guideState?.current_step);
    if (stored >= 0 && !steps[stored].complete && !steps[stored].skipped) return stored;
    return firstIncompleteIndex;
  }, [firstIncompleteIndex, guideState?.current_step, steps]);

  const currentStep = steps[currentIndex] || null;
  const completedCount = steps.filter((step) => step.complete).length;
  const completionPercent = steps.length
    ? Math.round((completedCount / steps.length) * 100)
    : 0;
  const allAdminStepsComplete =
    role === "admin" && steps.length > 0 && steps.every((step) => step.complete);

  const persist = useCallback(
    async (payload) => {
      if (!config) return null;
      const response = await guideService.updateState(config.key, payload);
      setGuideState(response);
      return response;
    },
    [config],
  );

  const loadGuide = useCallback(async () => {
    if (!enabled || !config) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [state, stats] = await Promise.all([
        guideService.getState(config.key),
        role === "admin"
          ? dashboardService.getTenantAdminAnalytics().catch(() => null)
          : Promise.resolve(null),
      ]);
      setGuideState(state);
      setAdminStats(stats);
    } finally {
      setLoading(false);
    }
  }, [config, enabled, role]);

  useEffect(() => {
    loadGuide();
  }, [loadGuide]);

  useEffect(() => {
    if (!enabled || loading || !config || !guideState) return;
    if (allAdminStepsComplete) {
      if (guideState.status !== "completed") {
        persist({ status: "completed", current_step: null });
      }
      setOpen(false);
      return;
    }
    if (["completed", "dismissed"].includes(guideState.status)) return;
    if (inFuture(guideState.remind_after)) return;
    setOpen(true);
  }, [
    allAdminStepsComplete,
    config,
    enabled,
    guideState,
    loading,
    persist,
  ]);

  useEffect(() => {
    const showGuide = () => {
      if (!config) return;
      setOpen(true);
    };
    window.addEventListener("weave:open-role-guide", showGuide);
    return () => window.removeEventListener("weave:open-role-guide", showGuide);
  }, [config]);

  const moveToIndex = useCallback(
    async (nextIndex) => {
      const nextStep = steps[nextIndex];
      if (!nextStep) {
        await persist({ status: "completed", current_step: null });
        setOpen(false);
        return;
      }
      await persist({
        status: "in_progress",
        current_step: nextStep.id,
        remind_after: null,
      });
    },
    [persist, steps],
  );

  const next = useCallback(async () => {
    if (!currentStep) return;
    await moveToIndex(currentIndex + 1);
  }, [currentIndex, currentStep, moveToIndex]);

  const previous = useCallback(async () => {
    if (currentIndex <= 0) return;
    await moveToIndex(currentIndex - 1);
  }, [currentIndex, moveToIndex]);

  const skipStep = useCallback(async () => {
    if (!currentStep) return;
    const skipped = Array.from(
      new Set([...(guideState?.skipped_steps || []), currentStep.id]),
    );
    const nextStep = steps[currentIndex + 1];
    if (!nextStep) {
      await persist({
        status: "completed",
        current_step: null,
        skipped_steps: skipped,
      });
      setOpen(false);
      return;
    }
    await persist({
      status: "in_progress",
      current_step: nextStep.id,
      skipped_steps: skipped,
      remind_after: null,
    });
  }, [currentIndex, currentStep, guideState?.skipped_steps, persist, steps]);

  const remindLater = useCallback(async () => {
    const remindAfter = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    await persist({
      status: "in_progress",
      current_step: currentStep?.id || null,
      remind_after: remindAfter,
    });
    setOpen(false);
  }, [currentStep?.id, persist]);

  const dismiss = useCallback(async () => {
    await persist({
      status: "dismissed",
      current_step: currentStep?.id || null,
      remind_after: null,
    });
    setOpen(false);
  }, [currentStep?.id, persist]);

  const openAction = useCallback(async () => {
    if (!currentStep?.to) return;
    await persist({
      status: "in_progress",
      current_step: currentStep.id,
      remind_after: null,
    });
    setOpen(false);
    navigate(currentStep.to);
  }, [currentStep, navigate, persist]);

  return {
    config,
    steps,
    currentStep,
    currentIndex,
    completionPercent,
    completedCount,
    guideState,
    loading,
    open,
    setOpen,
    next,
    previous,
    skipStep,
    remindLater,
    dismiss,
    openAction,
    refresh: loadGuide,
  };
}

export default useRoleGuide;
