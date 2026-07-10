import { api } from "./api";

export const brandingService = {
  getBranding: (options = {}) => api.get("/tenant-admin/branding", options),

  getEffectiveBranding: (options = {}) =>
    api.get("/tenant-admin/branding/effective", options),

  updateBranding: (payload, options = {}) =>
    api.patch("/tenant-admin/branding", payload, options),

  enableBranding: (options = {}) =>
    api.post("/tenant-admin/branding/enable", undefined, options),

  disableBranding: (options = {}) =>
    api.post("/tenant-admin/branding/disable", undefined, options),
};
