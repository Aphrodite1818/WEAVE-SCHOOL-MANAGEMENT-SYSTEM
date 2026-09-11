export function didCompleteInitialOnboarding({
  profileMode,
  wasRequired,
  nextStatus,
} = {}) {
  return (
    profileMode === "onboarding" &&
    wasRequired === true &&
    nextStatus?.onboarding_required === false
  );
}
