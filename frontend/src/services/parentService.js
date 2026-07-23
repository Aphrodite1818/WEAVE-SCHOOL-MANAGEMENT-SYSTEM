import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 100, 1), 100);

const buildParentQuery = ({ skip = 0, limit = 100, search, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(skip));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  return params.toString();
};

const buildInvitationQuery = ({ skip = 0, limit = 50, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(skip));
  params.set("limit", String(Math.min(Math.max(Number(limit) || 50, 1), 100)));
  if (status) params.set("status", status);
  return params.toString();
};

export const parentService = {
  registerAccount: (payload) =>
    api.post("/parents/accounts/register", payload, {
      auth: false,
      clearAuthOnUnauthorized: false,
      skipAuthRefresh: true,
    }),

  getInvitationContext: (token) =>
    api.get(`/parents/invitations/context?token=${encodeURIComponent(token)}`, {
      auth: false,
      clearAuthOnUnauthorized: false,
      skipAuthRefresh: true,
    }),

  acceptInvitation: (invitationToken, admissionNumber) =>
    api.post("/parents/accounts/me/invitations/accept", {
      invitation_token: invitationToken,
      admission_number: admissionNumber,
    }),

  getParents: (options = {}) =>
    api.get(`/tenant-admin/parents?${buildParentQuery(options)}`),

  createParent: (payload) =>
    api.post("/tenant-admin/parents", payload),

  createInvitation: (payload) =>
    api.post("/parents/invitations", payload),

  listInvitations: (options = {}) =>
    api.get(`/parents/invitations?${buildInvitationQuery(options)}`),

  revokeInvitation: (invitationId) =>
    api.post(`/parents/invitations/${invitationId}/revoke`),

  listMemberships: (options = {}) =>
    api.get(`/parents/memberships?${buildParentQuery(options)}`),

  getMyParent: (requestOptions) =>
    api.get("/parents/me", requestOptions),

  updateMyParentProfile: (payload) =>
    api.patch("/parents/me/profile", payload),

  getMyStudents: (requestOptions) =>
    api.get("/parents/me/students", requestOptions),

  getMyStudentLinkRequests: (requestOptions) =>
    api.get("/parents/me/student-link-requests", requestOptions),

  getParent: (parentId) =>
    api.get(`/tenant-admin/parents/${parentId}`),

  updateParent: (parentId, payload) =>
    api.patch(`/tenant-admin/parents/${parentId}`, payload),

  deleteParent: (parentId) =>
    api.delete(`/tenant-admin/parents/${parentId}`),
};
