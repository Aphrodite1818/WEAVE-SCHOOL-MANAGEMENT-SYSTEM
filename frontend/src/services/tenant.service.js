import { api } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberRecord,
} from "./patchPayload";

const tenantsById = new Map();

export const tenantService = {
  registerTenant: (data) => api.post("/tenants/register", data, { auth: false }),

  getTenant: async (tenantId) => {
    const response = await api.get(`/tenants/${tenantId}`);
    return rememberRecord(tenantsById, response);
  },

  updateTenant: async (tenantId, data) => {
    const key = String(tenantId);
    const current = tenantsById.get(key);
    const changes = buildChangedPatch(current, data);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(`/tenants/${tenantId}`, changes);
    tenantsById.set(key, mergePatchResult(current, changes, response));
    return response;
  },
};
