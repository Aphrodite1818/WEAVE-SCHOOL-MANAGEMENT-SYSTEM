export function visibleGuideSteps(steps, { attendanceEnabled, features, completionMap, role }) {
  return steps.filter((step) =>
    (attendanceEnabled || step.id !== "attendance") &&
    (!step.feature || features?.[step.feature] === true) &&
    !(role === "admin" && step.id === "departments" && completionMap?.departments === null),
  );
}
