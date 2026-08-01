import { useCallback, useEffect, useMemo, useState } from "react";

import { guideService } from "../../services/guideService";
import { guideForRole } from "./roleGuideConfig";

const hasOwn = (value, key) =>
  Boolean(value) && Object.prototype.hasOwnProperty.call(value, key);

export function useRoleGuide({
  role,
  enabled = true,
  completionMap = null,
} = {}) {
  const config = guideForRole(role);
  const [guideState, setGuideState] = useState(null);
  const [loading, setLoading] = useState(Boolean(config && enabled));

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
      setGuideState(await guideService.getState(config.key));
    } finally {
      setLoading(false);
    }
  }, [config, enabled]);

  useEffect(() => {
    loadGuide();
  }, [loadGuide]);

  const steps = useMemo(() => {
    if (!config) return [];
    const skipped = new Set(guideState?.skipped_steps || []);
    const storedIndex = Math.max(
      0,
      config.steps.findIndex((step) => step.id === guideState?.current_step),
    );

    return config.steps.map((step, index) => ({
      ...step,
      complete: hasOwn(completionMap, step.id)
        ? Boolean(completionMap[step.id])
        : guideState?.status === "completed" || index < storedIndex,
      skipped: skipped.has(step.id),
    }));
  }, [completionMap, config, guideState]);

  const firstPendingIndex = useMemo(() => {
    const index = steps.findIndex((step) => !step.complete && !step.skipped);
    return index >= 0 ? index : Math.max(steps.length - 1, 0);
  }, [steps]);

  const currentIndex = useMemo(() => {
    if (!steps.length) return 0;
    const storedIndex = steps.findIndex(
      (step) => step.id === guideState?.current_step,
    );
    if (
      storedIndex >= 0 &&
      !steps[storedIndex].complete &&
      !steps[storedIndex].skipped
    ) {
      return storedIndex;
    }
    return firstPendingIndex;
  }, [firstPendingIndex, guideState?.current_step, steps]);

  const currentStep = steps[currentIndex] || null;
  const completedCount = steps.filter((step) => step.complete).length;
  const skippedCount = steps.filter((step) => step.skipped && !step.complete).length;
  const resolvedCount = completedCount + skippedCount;
  const completionPercent = steps.length
    ? Math.round((resolvedCount / steps.length) * 100)
    : 0;
  const allResolved =
    steps.length > 0 && steps.every((step) => step.complete || step.skipped);

  useEffect(() => {
    if (
      !enabled ||
      loading ||
      !guideState ||
      !allResolved ||
      guideState.status === "completed"
    ) {
      return;
    }
    persist({ status: "completed", current_step: null, remind_after: null });
  }, [allResolved, enabled, guideState, loading, persist]);

  const start = useCallback(async () => {
    if (!config) return null;
    const initialStep =
      steps.find((step) => !step.complete && !step.skipped) || steps[0];
    return persist({
      status: "in_progress",
      current_step: initialStep?.id || null,
      remind_after: null,
    });
  }, [config, persist, steps]);

  const moveTo = useCallback(
    async (stepId) => {
      if (!steps.some((step) => step.id === stepId)) return null;
      return persist({
        status: "in_progress",
        current_step: stepId,
        remind_after: null,
      });
    },
    [persist, steps],
  );

  const advanceFrom = useCallback(
    async (stepId) => {
      const index = steps.findIndex((step) => step.id === stepId);
      const nextStep = steps
        .slice(Math.max(index + 1, 0))
        .find((step) => !step.complete && !step.skipped);
      if (!nextStep) {
        return persist({
          status: "completed",
          current_step: null,
          remind_after: null,
        });
      }
      return moveTo(nextStep.id);
    },
    [moveTo, persist, steps],
  );

  const skipStep = useCallback(
    async (stepId = currentStep?.id) => {
      if (!stepId) return null;
      const skippedSteps = Array.from(
        new Set([...(guideState?.skipped_steps || []), stepId]),
      );
      const index = steps.findIndex((step) => step.id === stepId);
      const nextStep = steps
        .slice(Math.max(index + 1, 0))
        .find(
          (step) =>
            !step.complete &&
            !skippedSteps.includes(step.id),
        );
      return persist({
        status: nextStep ? "in_progress" : "completed",
        current_step: nextStep?.id || null,
        skipped_steps: skippedSteps,
        remind_after: null,
      });
    },
    [currentStep?.id, guideState?.skipped_steps, persist, steps],
  );

  const dismiss = useCallback(
    () =>
      persist({
        status: "dismissed",
        current_step: currentStep?.id || null,
        remind_after: null,
      }),
    [currentStep?.id, persist],
  );

  const finish = useCallback(
    () =>
      persist({
        status: "completed",
        current_step: null,
        remind_after: null,
      }),
    [persist],
  );

  return {
    config,
    steps,
    currentStep,
    currentIndex,
    completedCount,
    skippedCount,
    resolvedCount,
    completionPercent,
    guideState,
    loading,
    shouldAutoRedirect:
      enabled && !loading && guideState?.status === "not_started",
    shouldShowBanner:
      enabled && !loading && guideState?.status === "in_progress",
    start,
    moveTo,
    advanceFrom,
    skipStep,
    dismiss,
    finish,
    refresh: loadGuide,
  };
}

export default useRoleGuide;
