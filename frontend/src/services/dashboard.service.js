import { api, authSession } from "./api";

const DASHBOARD_CACHE_TTL_MS = 60 * 1000;
const DASHBOARD_CACHE_PREFIX = "learnly:dashboard-metrics";

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

const readCachedDashboard = (key) => {
  try {
    const rawValue = window.sessionStorage.getItem(key);
    if (!rawValue) return null;

    const cached = JSON.parse(rawValue);
    if (!cached?.timestamp || cached?.data === undefined) return null;

    if (Date.now() - cached.timestamp > DASHBOARD_CACHE_TTL_MS) {
      window.sessionStorage.removeItem(key);
      return null;
    }

    return cached.data;
  } catch {
    window.sessionStorage.removeItem(key);
    return null;
  }
};

const writeCachedDashboard = (key, data) => {
  try {
    window.sessionStorage.setItem(
      key,
      JSON.stringify({ timestamp: Date.now(), data })
    );
  } catch {
    // Cache storage is best-effort only. The dashboard must still work without it.
  }
};

const getDashboardMetrics = async (endpoint, requestOptions = {}) => {
  const cacheKey = getDashboardCacheKey(endpoint);
  const cached = readCachedDashboard(cacheKey);

  if (cached) return cached;

  const fresh = await api.get(endpoint, requestOptions);
  writeCachedDashboard(cacheKey, fresh);
  return fresh;
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
