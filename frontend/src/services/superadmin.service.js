import { api } from "./api";

const buildQuery = (params) => {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
};

export const superadminService = {
  getAnalyticsOverview: (requestOptions) => api.get("/metrics/superadmin/dashboard", requestOptions),

  getSecurityOverview: (requestOptions) => api.get("/superadmin/security/overview", requestOptions),

  getPlatformControl: (requestOptions) => api.get("/superadmin/platform-control", requestOptions),

  enablePlatformLockdown: (data) => api.post("/superadmin/platform-control/lockdown", data),

  disablePlatformLockdown: (data) => api.post("/superadmin/platform-control/unlock", data),

  createTenant: (data) => api.post("/superadmin/tenants", data),

  getTenants: (skip = 0, limit = 50, includeDeleted = true, requestOptions) =>
    api.get(
      `/superadmin/tenants${buildQuery({
        skip,
        limit,
        include_deleted: includeDeleted,
      })}`,
      requestOptions
    ),

  getTenant: (tenantId, includeDeleted = true) =>
    api.get(
      `/superadmin/tenants/${tenantId}${buildQuery({
        include_deleted: includeDeleted,
      })}`
    ),

  updateTenantStatus: (tenantId, statusData) =>
    api.patch(`/superadmin/tenants/${tenantId}/status`, statusData),

  deleteTenant: (tenantId) => api.delete(`/superadmin/tenants/${tenantId}`),

  restoreTenant: (tenantId) =>
    api.patch(`/superadmin/tenants/${tenantId}/restore`, {}),

  getSuperadmins: (skip = 0, limit = 100, requestOptions) =>
    api.get(`/superadmin/superadmins${buildQuery({ skip, limit })}`, requestOptions),

  inviteSuperadmin: (data) => api.post("/superadmin/superadmins/invite", data),
};
