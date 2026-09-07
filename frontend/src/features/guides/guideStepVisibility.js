export function visibleGuideSteps(
  steps,
  { runtimeFeatures = {}, features, completionMap, role } = {},
) {
  return steps.filter((step) =>
    (!step.runtimeFeature || runtimeFeatures?.[step.runtimeFeature] !== false) &&
    (!step.feature || features?.[step.feature] === true) &&
    !(role === "admin" && step.id === "departments" && completionMap?.departments === null),
  );
}
