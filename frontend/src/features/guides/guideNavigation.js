const GUIDE_RETURN_STORAGE_KEY = "weave:guide-return";

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
