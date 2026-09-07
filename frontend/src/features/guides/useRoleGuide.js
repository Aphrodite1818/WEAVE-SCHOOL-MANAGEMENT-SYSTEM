import { useSubscription } from "../subscriptions/useSubscription";
import { visibleGuideSteps } from "./guideStepVisibility";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRuntimeConfig } from "../../hooks/useRuntimeConfig";
import { guideService } from "../../services/guideService";
import { hasGuideExitSuppression } from "./guideNavigation";
import { guideForRole } from "./roleGuideConfig";

export const GUIDE_STATE_CHANGED_EVENT = "weave:guide-state-changed";

const hasOwn = (value, key) =>
  Boolean(value) && Object.prototype.hasOwnProperty.call(value, key);

export function useRoleGuide({
  role,
  enabled = true,
  completionMap = null,
  allowCompletedCurrentStep = false,
  allowSkippedCurrentStep = false,
} = {}) {
  const normalizedRole = String(role || "").toLowerCase();
  const subscription = useSubscription();
  const entitledFeatures = subscription?.entitlements?.features;
  const baseConfig = guideForRole(normalizedRole);
  const runtimeConfig = useRuntimeConfig();
  const runtimeFeatures = runtimeConfig?.features || {};
  const config = useMemo(() => {
    if (!baseConfig) return baseConfig;

    return {
      ...baseConfig,
      steps: visibleGuideSteps(baseConfig.steps, {
        runtimeFeatures,
        features: entitledFeatures,
        subscription,
        completionMap,
        role: normalizedRole,
      }),
    };
  }, [
    baseConfig,
    normalizedRole,
    entitledFeatures,
    subscription,
    completionMap,
    runtimeFeatures,
  ]);
  const [guideState, setGuideState] = useState(null);
  const [loading, setLoading] = useState(Boolean(config && enabled));
  const stateVersionRef = useRef(0);

  const publishState = useCallback(
    (state) => {
      if (!config || !state) return;
      stateVersionRef.current += 1;
      setGuideState(state);
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent(GUIDE_STATE_CHANGED_EVENT, {
            detail: { key: config.key, state },
          }),
        );
      }
    },
    [config],
  );

  const persist = useCallback(
    async (payload) => {
      if (!config) return null;
      const response = await guideService.updateState(config.key, payload);
      publishState(response);
      return response;
    },
    [config, publishState],
  );

  const loadGuide = useCallback(async () => {
    if (!enabled || !config) {
      setLoading(false);
      return;
    }

    const requestVersion = stateVersionRef.current;
    setLoading(true);
    try {
      const response = await guideService.getState(config.key);
      if (stateVersionRef.current === requestVersion) {
        setGuideState(response);
      }
    } finally {
      setLoading(false);
    }
  }, [config, enabled]);

  useEffect(() => {
    loadGuide();
  }, [loadGuide]);

  useEffect(() => {
    if (typeof window === "undefined" || !config) return undefined;
    const handleStateChange = (event) => {
      if (event?.detail?.key !== config.key || !event.detail.state) return;
      stateVersionRef.current += 1;
      setGuideState(event.detail.state);
    };
    window.addEventListener(GUIDE_STATE_CHANGED_EVENT, handleStateChange);
    return () => window.removeEventListener(GUIDE_STATE_CHANGED_EVENT, handleStateChange);
  }, [config]);

  useEffect(() => {
    if (typeof window === "undefined" || !enabled || !config) return undefined;
    const retryPendingState = async () => {
      const response = await guideService.retryPendingState(config.key);
      publishState(response);
    };
    window.addEventListener("online", retryPendingState);
    return () => window.removeEventListener("online", retryPendingState);
  }, [config, enabled, publishState]);

  const steps = useMemo(() => {
    if (!config || !baseConfig) return [];
    const skipped = new Set(guideState?.skipped_steps || []);
    const storedIndex = baseConfig.steps.findIndex(
      (step) => step.id === guideState?.current_step,
    );

    return config.steps.map((step) => {
      const baseIndex = baseConfig.steps.findIndex(
        (configuredStep) => configuredStep.id === step.id,
      );
      return {
        ...step,
        complete: hasOwn(completionMap, step.id)
          ? Boolean(completionMap[step.id])
          : normalizedRole === "admin"
            ? false
            : guideState?.status === "completed" ||
              (storedIndex >= 0 && baseIndex >= 0 && baseIndex < storedIndex),
        skipped: skipped.has(step.id),
      };
    });
  }, [baseConfig, completionMap, config, guideState, normalizedRole]);

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
      (allowCompletedCurrentStep || !steps[storedIndex].complete) &&
      (allowSkippedCurrentStep || !steps[storedIndex].skipped)
    ) {
      return storedIndex;
    }
    return firstPendingIndex;
  }, [
    allowCompletedCurrentStep,
    allowSkippedCurrentStep,
    firstPendingIndex,
    guideState?.current_step,
    steps,
  ]);

  const currentStep = steps[currentIndex] || null;
  const completedCount = steps.filter((step) => step.complete).length;
  const skippedCount = steps.filter((step) => step.skipped && !step.complete).length;
  const resolvedCount = completedCount + skippedCount;
  const completionPercent = steps.length
    ? Math.round((resolvedCount / steps.length) * 100)
    : 0;
  const allResolved =
    steps.length > 0 &&
    steps
      .filter((step) => !step.optional)
      .every(
        (step) =>
          step.complete || (normalizedRole !== "admin" && step.skipped),
      );
  const syncPending = Boolean(guideState?.sync_pending);

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
    if (!config || ["completed", "dismissed"].includes(guideState?.status)) {
      return guideState;
    }
    const initialStep =
      steps.find((step) => !step.complete && !step.skipped) || steps[0];
    return persist({
      status: "in_progress",
      current_step: initialStep?.id || null,
      remind_after: null,
    });
  }, [config, guideState, persist, steps]);

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
            !step.complete && !skippedSteps.includes(step.id),
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
    syncPending,
    shouldAutoRedirect:
      enabled &&
      !loading &&
      !syncPending &&
      guideState?.status === "not_started" &&
      !hasGuideExitSuppression(role),
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
