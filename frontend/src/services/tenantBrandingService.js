import { api } from "./api";

export const tenantBrandingService = {
  getEffective: (options) => api.get("/workspace/branding", options),
  getAdmin: () => api.get("/tenant-admin/branding"),
  update: (payload) => api.patch("/tenant-admin/branding", payload),
  enable: () => api.post("/tenant-admin/branding/enable"),
  disable: () => api.post("/tenant-admin/branding/disable"),
  reset: () => api.post("/tenant-admin/branding/reset"),
};
