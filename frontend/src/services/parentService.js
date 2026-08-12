import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 50, 1), 100);

const normalizeParentMembershipStatus = (status) =>
  status === "ended" ? "inactive" : status;

const buildParentQuery = ({ skip = 0, limit = 50, search, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  if (status) params.set("status", normalizeParentMembershipStatus(status));
  return params.toString();
};

const buildInvitationQuery = ({ skip = 0, limit = 50, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
  if (status) params.set("status", status);
  return params.toString();
};

const buildPageQuery = ({ skip = 0, limit = 50 } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
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
    api.post(
      "/parents/accounts/me/invitations/accept",
      { invitation_token: invitationToken },
      {
        headers: {
          "X-Student-Admission-Number": admissionNumber,
        },
      },
    ),

  getParents: (options = {}) =>
    api.get(`/parents/memberships?${buildParentQuery(options)}`),

  createInvitation: (payload) =>
    api.post("/parents/invitations", payload),

  listInvitations: (options = {}) =>
    api.get(`/parents/invitations?${buildInvitationQuery(options)}`),

  revokeInvitation: (invitationId) =>
    api.post(`/parents/invitations/${invitationId}/revoke`),

  listMemberships: (options = {}) =>
    api.get(`/parents/memberships?${buildParentQuery(options)}`),

  getMembership: (membershipId) =>
    api.get(`/parents/memberships/${membershipId}`),

  listMembershipLinks: (membershipId) =>
    api.get(`/parents/memberships/${membershipId}/student-links`),

  updateParentLink: (linkId, payload) =>
    api.patch(`/tenant-admin/student-parent-links/${linkId}`, payload),

  endMembership: (membershipId, reason) =>
    api.post(`/parents/memberships/${membershipId}/end`, { reason }),

  reactivateMembership: (membershipId, reason) =>
    api.post(`/parents/memberships/${membershipId}/reactivate`, { reason }),

  listPendingLinkRequests: (options = {}) =>
    api.get(`/parents/student-link-requests?${buildPageQuery(options)}`),

  decideLinkRequest: (requestId, payload) =>
    api.post(`/tenant-admin/student-parent-link-requests/${requestId}/decision`, payload),

  endParentLink: (linkId, reason) =>
    api.post(`/parents/student-parent-links/${linkId}/end`, { reason }),

  reactivateParentLink: (linkId, payload) =>
    api.post(`/parents/student-parent-links/${linkId}/reactivate`, payload),

  getMyParent: (requestOptions) =>
    api.get("/parents/me", requestOptions),

  updateMyParentProfile: (payload) =>
    api.patch("/parents/accounts/me/profile", payload),

  getMyStudents: (requestOptions) =>
    api.get("/parents/me/students", requestOptions),

  getChildProgression: (studentId, requestOptions) =>
    api.get(`/parents/academics/students/${studentId}/progression`, requestOptions),

  getMyStudentLinkRequests: (requestOptions) =>
    api.get("/parents/me/student-link-requests", requestOptions),

  getParent: (parentId) =>
    api.get(`/parents/memberships/${parentId}`),
};
