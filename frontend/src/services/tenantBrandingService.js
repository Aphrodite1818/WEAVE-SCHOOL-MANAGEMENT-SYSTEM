import { api, authSession } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
} from "./patchPayload";

const adminBrandingSnapshots = new Map();

const rememberAdminBranding = (response) => {
  if (response) adminBrandingSnapshots.set(adminBrandingCacheKey(response), response);
  return response;
};

const adminBrandingCacheKey = (response = null) => {
  const user = authSession.getUser() || {};
  return String(
    response?.tenant_id ||
      user?.tenant_id ||
      user?.tenant?.id ||
      "global",
  );
};

const getCachedAdminBranding = () =>
  adminBrandingSnapshots.get(adminBrandingCacheKey()) || null;

export const tenantBrandingService = {
  getEffective: (options) => api.get("/workspace/branding", options),
  getAdmin: async ({ force = false } = {}) => {
    if (!force) {
      const cached = getCachedAdminBranding();
      if (cached) return cached;
    }
    return rememberAdminBranding(await api.get("/tenant-admin/branding"));
  },
  update: async (payload) => {
    const adminBrandingSnapshot = getCachedAdminBranding();
    const changes = buildChangedPatch(adminBrandingSnapshot, payload);
    if (!hasPatchChanges(changes)) return adminBrandingSnapshot;

    const response = await api.patch("/tenant-admin/branding", changes);
    return rememberAdminBranding(mergePatchResult(
      adminBrandingSnapshot,
      changes,
      response,
    ));
  },
  enable: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/enable")),
  disable: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/disable")),
  reset: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/reset")),
};
