import { api, authSession } from "./api";

const DASHBOARD_CACHE_PREFIX = "learnly:dashboard-metrics";
const dashboardMemoryCache = new Map();
let cacheInvalidationBound = false;

const getActorCacheScope = () => {
  const user = authSession.getUser() || {};
  return [
    user.role || authSession.getRole() || "unknown-role",
    user.tenant_id || "global",
    user.id || user.actor_id || user.email || user.admission_number || "anonymous",
  ].join(":");
};

const getDashboardCacheKey = (endpoint) =>
  `${DASHBOARD_CACHE_PREFIX}:${getActorCacheScope()}:${endpoint}`;

const bindCacheInvalidation = () => {
  if (cacheInvalidationBound || typeof window === "undefined") return;
  cacheInvalidationBound = true;

  window.addEventListener("pagehide", () => dashboardMemoryCache.clear());
  window.addEventListener("beforeunload", () => dashboardMemoryCache.clear());
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) dashboardMemoryCache.clear();
  });
};

const getDashboardMetrics = async (endpoint, requestOptions = {}) => {
  bindCacheInvalidation();

  const cacheKey = getDashboardCacheKey(endpoint);
  const cached = dashboardMemoryCache.get(cacheKey);

  if (cached) return cached;

  const fresh = await api.get(endpoint, requestOptions);
  dashboardMemoryCache.set(cacheKey, fresh);
  return fresh;
};

export const clearDashboardMetricsCache = () => {
  dashboardMemoryCache.clear();
};

export const dashboardService = {
  getTenantAdminAnalytics: (requestOptions) =>
    getDashboardMetrics("/metrics/tenant-admin/dashboard", requestOptions),

  getSuperadminAnalytics: (requestOptions) =>
    getDashboardMetrics("/metrics/superadmin/dashboard", requestOptions),

  getTeacherAnalytics: (requestOptions) =>
    getDashboardMetrics("/metrics/teacher/dashboard", requestOptions),

  getParentAnalytics: (requestOptions) =>
    getDashboardMetrics("/metrics/parent/dashboard", requestOptions),

  getStudentAnalytics: (requestOptions) =>
    getDashboardMetrics("/metrics/student/dashboard", requestOptions),
};
