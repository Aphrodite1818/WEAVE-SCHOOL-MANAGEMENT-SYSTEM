import { api } from "./api";
import {
  clearDashboardSessionCache,
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "./dashboardSessionCache";

const getDashboardMetrics = async (endpoint, requestOptions = {}) =>
  getCachedDashboardBundle(
    getDashboardSessionCacheKey(`metrics:${endpoint}`),
    () => api.get(endpoint, requestOptions),
  );

export const clearDashboardMetricsCache = () => {
  clearDashboardSessionCache();
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
