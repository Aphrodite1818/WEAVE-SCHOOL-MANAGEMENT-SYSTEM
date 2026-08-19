import { api } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
} from "./patchPayload";

let adminBrandingSnapshot = null;

const rememberAdminBranding = (response) => {
  if (response) adminBrandingSnapshot = response;
  return response;
};

export const tenantBrandingService = {
  getEffective: (options) => api.get("/workspace/branding", options),
  getAdmin: async () =>
    rememberAdminBranding(await api.get("/tenant-admin/branding")),
  update: async (payload) => {
    const changes = buildChangedPatch(adminBrandingSnapshot, payload);
    if (!hasPatchChanges(changes)) return adminBrandingSnapshot;

    const response = await api.patch("/tenant-admin/branding", changes);
    adminBrandingSnapshot = mergePatchResult(
      adminBrandingSnapshot,
      changes,
      response,
    );
    return response;
  },
  enable: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/enable")),
  disable: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/disable")),
  reset: async () =>
    rememberAdminBranding(await api.post("/tenant-admin/branding/reset")),
};
