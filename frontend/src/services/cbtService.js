import { api } from "./api";

export const cbtService = {
  createPairingCode: () => api.post("/cbt/pairing/codes"),
  verifyPairingCode: (payload) => api.post("/cbt/pairing/verify", payload, { auth: false }),
  listServers: () => api.get("/cbt/servers"),
  getServer: (serverId) => api.get(`/cbt/servers/${encodeURIComponent(serverId)}`),
  suspendServer: (serverId) => api.post(`/cbt/servers/${encodeURIComponent(serverId)}/suspend`),
  reactivateServer: (serverId) => api.post(`/cbt/servers/${encodeURIComponent(serverId)}/reactivate`),
  revokeServer: (serverId, payload = {}) =>
    api.post(`/cbt/servers/${encodeURIComponent(serverId)}/revoke`, payload),
  rotateCredential: (serverId) =>
    api.post(`/cbt/servers/${encodeURIComponent(serverId)}/rotate-credential`),
};

export default cbtService;
