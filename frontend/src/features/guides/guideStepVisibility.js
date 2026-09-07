import { isFeatureAvailable } from "../navigation/featureAvailability.js";

export function visibleGuideSteps(
  steps,
  {
    runtimeFeatures = {},
    features,
    subscription,
    completionMap,
    role,
  } = {},
) {
  return steps.filter(
    (step) =>
      isFeatureAvailable(step, {
        runtimeFeatures,
        entitledFeatures: features,
        subscription,
      }) &&
      !(
        role === "admin" &&
        step.id === "departments" &&
        completionMap?.departments === null
      ),
  );
}
