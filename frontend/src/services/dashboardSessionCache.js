
import { authSession } from "./api";

const DEFAULT_DASHBOARD_CACHE_TTL_MS = 10 * 60 * 1000;
const DASHBOARD_BUNDLE_CACHE_PREFIX = "weave:dashboard-session:v2";
const dashboardBundleCache = new Map();
let invalidationBound = false;
let lastActorCacheScope = null;
let cacheGeneration = 0;

const getActorCacheScope = () => {
  const user = authSession.getUser() || {};
  return [
    user.role || authSession.getRole() || "unknown-role",
    user.tenant_id || "global",
    user.id || user.actor_id || user.email || user.admission_number || "anonymous",
  ].join(":");
};

const storageKey = (cacheKey) => `${DASHBOARD_BUNDLE_CACHE_PREFIX}:snapshot:${cacheKey}`;

const removeStoredScope = (scope) => {
  if (typeof window === "undefined") return;
  const prefix = `${DASHBOARD_BUNDLE_CACHE_PREFIX}:snapshot:${scope}:`;
  Array.from({ length: window.sessionStorage.length }, (_, index) => window.sessionStorage.key(index))
    .filter((key) => key.startsWith(prefix))
    .forEach((key) => window.sessionStorage.removeItem(key));
};

const clearCache = () => {
  cacheGeneration += 1;
  dashboardBundleCache.clear();
  removeStoredScope(lastActorCacheScope || getActorCacheScope());
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("weave:dashboard-cache-invalidated"));
  }
};

const resolveActorScope = () => {
  const nextScope = getActorCacheScope();
  if (lastActorCacheScope && lastActorCacheScope !== nextScope) {
    cacheGeneration += 1;
    dashboardBundleCache.clear();
    removeStoredScope(lastActorCacheScope);
  }
  lastActorCacheScope = nextScope;
  return nextScope;
};

const bindCacheInvalidation = () => {
  if (invalidationBound || typeof window === "undefined") return;
  invalidationBound = true;
  window.addEventListener("weave:dashboard-cache-clear", clearCache);
};

const resolveCacheKey = (key) => {
  if (String(key).startsWith(`${DASHBOARD_BUNDLE_CACHE_PREFIX}:`)) return key;
  return `${resolveActorScope()}:${key}`;
};

const readSnapshot = (cacheKey, now) => {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(storageKey(cacheKey)) || "null");
    if (!parsed || parsed.expiresAt <= now || parsed.value === undefined) {
      window.sessionStorage.removeItem(storageKey(cacheKey));
      return null;
    }
    return parsed;
  } catch {
    window.sessionStorage.removeItem(storageKey(cacheKey));
    return null;
  }
};

const writeSnapshot = (cacheKey, value, expiresAt) => {
  try {
    window.sessionStorage.setItem(
      storageKey(cacheKey),
      JSON.stringify({ value, expiresAt }),
    );
  } catch {
    // Large or unavailable session storage must not break the dashboard.
  }
};

export const getDashboardSessionCacheKey = (name) => name;

export const clearDashboardSessionCache = () => {
  clearCache();
  lastActorCacheScope = getActorCacheScope();
};

export const invalidateDashboardSessionCache = clearDashboardSessionCache;

export const getCachedDashboardBundle = async (
  key,
  loader,
  { ttlMs = DEFAULT_DASHBOARD_CACHE_TTL_MS, force = false } = {},
) => {
  bindCacheInvalidation();
  const cacheKey = resolveCacheKey(key);
  const now = Date.now();
  const memory = dashboardBundleCache.get(cacheKey);

  if (!force && memory?.value !== undefined && memory.expiresAt > now) {
    return memory.value;
  }
  if (!force && memory?.promise) return memory.promise;

  if (!force) {
    const snapshot = readSnapshot(cacheKey, now);
    if (snapshot) {
      dashboardBundleCache.set(cacheKey, { ...snapshot, promise: null });
      return snapshot.value;
    }
  }

  const generation = cacheGeneration;
  const promise = Promise.resolve()
    .then(loader)
    .then((value) => {
      // A request started before a write or actor change cannot restore stale data.
      if (generation !== cacheGeneration) return value;
      const expiresAt = Date.now() + ttlMs;
      dashboardBundleCache.set(cacheKey, { value, expiresAt, promise: null });
      writeSnapshot(cacheKey, value, expiresAt);
      return value;
    })
    .catch((error) => {
      const current = dashboardBundleCache.get(cacheKey);
      if (current?.promise === promise) dashboardBundleCache.delete(cacheKey);
      throw error;
    });

  dashboardBundleCache.set(cacheKey, {
    value: force ? memory?.value : undefined,
    expiresAt: now + ttlMs,
    promise,
  });
  return promise;
};
