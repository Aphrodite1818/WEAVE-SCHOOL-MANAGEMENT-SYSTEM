import { authSession } from "./api";

const DEFAULT_DASHBOARD_CACHE_TTL_MS = 10 * 60 * 1000;
const DASHBOARD_BUNDLE_CACHE_PREFIX = "learnly:dashboard-session";

const dashboardBundleCache = new Map();
let invalidationBound = false;

const getActorCacheScope = () => {
  const user = authSession.getUser() || {};

  return [
    user.role || authSession.getRole() || "unknown-role",
    user.tenant_id || "global",
    user.id || user.actor_id || user.email || user.admission_number || "anonymous",
  ].join(":");
};

const bindCacheInvalidation = () => {
  if (invalidationBound || typeof window === "undefined") return;
  invalidationBound = true;

  const clearCache = () => dashboardBundleCache.clear();

  window.addEventListener("pagehide", clearCache);
  window.addEventListener("beforeunload", clearCache);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearCache();
  });
};

const resolveCacheKey = (key) => {
  if (String(key).startsWith(`${DASHBOARD_BUNDLE_CACHE_PREFIX}:`)) return key;
  return `${DASHBOARD_BUNDLE_CACHE_PREFIX}:${getActorCacheScope()}:${key}`;
};

export const getDashboardSessionCacheKey = (name) => name;

export const clearDashboardSessionCache = () => {
  dashboardBundleCache.clear();
};

export const getCachedDashboardBundle = async (
  key,
  loader,
  { ttlMs = DEFAULT_DASHBOARD_CACHE_TTL_MS } = {},
) => {
  bindCacheInvalidation();

  const cacheKey = resolveCacheKey(key);
  const now = Date.now();
  const cached = dashboardBundleCache.get(cacheKey);

  if (cached?.value !== undefined && cached.expiresAt > now) {
    return cached.value;
  }

  if (cached?.promise) {
    return cached.promise;
  }

  const promise = Promise.resolve()
    .then(loader)
    .then((value) => {
      dashboardBundleCache.set(cacheKey, {
        value,
        expiresAt: Date.now() + ttlMs,
        promise: null,
      });
      return value;
    })
    .catch((error) => {
      const current = dashboardBundleCache.get(cacheKey);
      if (current?.promise === promise) {
        dashboardBundleCache.delete(cacheKey);
      }
      throw error;
    });

  dashboardBundleCache.set(cacheKey, {
    value: undefined,
    expiresAt: now + ttlMs,
    promise,
  });

  return promise;
};
