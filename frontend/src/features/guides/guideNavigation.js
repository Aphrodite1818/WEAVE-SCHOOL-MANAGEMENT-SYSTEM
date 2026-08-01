const GUIDE_RETURN_STORAGE_KEY = "weave:guide-return";
const GUIDE_EXIT_STORAGE_KEY = "weave:guide-exit";
const GUIDE_EXIT_TTL_MS = 5 * 60 * 1000;

export function saveGuideReturn(value) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(GUIDE_RETURN_STORAGE_KEY, JSON.stringify(value));
}

export function readGuideReturn() {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(GUIDE_RETURN_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed?.route || !parsed?.role) return null;
    return parsed;
  } catch {
    window.sessionStorage.removeItem(GUIDE_RETURN_STORAGE_KEY);
    return null;
  }
}

export function clearGuideReturn() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(GUIDE_RETURN_STORAGE_KEY);
}


export function markGuideExit(role, destination) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(
    GUIDE_EXIT_STORAGE_KEY,
    JSON.stringify({ role, destination, createdAt: Date.now() }),
  );
}

export function hasGuideExitSuppression(role) {
  if (typeof window === "undefined") return false;
  const raw = window.sessionStorage.getItem(GUIDE_EXIT_STORAGE_KEY);
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw);
    const valid =
      parsed?.role === role &&
      Number.isFinite(parsed?.createdAt) &&
      Date.now() - parsed.createdAt <= GUIDE_EXIT_TTL_MS;
    if (!valid) window.sessionStorage.removeItem(GUIDE_EXIT_STORAGE_KEY);
    return valid;
  } catch {
    window.sessionStorage.removeItem(GUIDE_EXIT_STORAGE_KEY);
    return false;
  }
}

export function leaveGuideRoute(role, destination, { replace = false } = {}) {
  if (typeof window === "undefined") return;
  markGuideExit(role, destination);
  if (replace) window.location.replace(destination);
  else window.location.assign(destination);
}
