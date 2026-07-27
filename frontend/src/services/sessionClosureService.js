import { api } from "./api";

export const sessionClosureService = {
  getAudit: (sessionId, requestOptions) =>
    api.get(
      `/tenant-admin/academics/sessions/${sessionId}/closure-audit`,
      requestOptions,
    ),

  startClosing: (sessionId, idempotencyKey) =>
    api.post(`/tenant-admin/academics/sessions/${sessionId}/start-closing`, {
      confirmation: "START_SESSION_CLOSING",
      idempotency_key: idempotencyKey,
    }),

  getStatus: (sessionId, requestOptions) =>
    api.get(
      `/tenant-admin/academics/sessions/${sessionId}/closing-status`,
      requestOptions,
    ),

  retryProgression: (sessionId) =>
    api.post(
      `/tenant-admin/academics/sessions/${sessionId}/retry-progression`,
      { confirmation: "RETRY_SESSION_PROGRESSION" },
    ),

  finalizeClose: (sessionId) =>
    api.post(`/tenant-admin/academics/sessions/${sessionId}/finalize-close`, {
      confirmation: "FINALIZE_SESSION_CLOSE",
    }),
};

export default sessionClosureService;
