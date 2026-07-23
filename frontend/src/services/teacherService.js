import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 100, 1), 100);

const buildTeacherQuery = ({ skip = 0, limit = 100, search, status } = {}) => {
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

export const teacherService = {
  registerAccount: (payload) =>
    api.post("/teachers/accounts/register", payload, {
      auth: false,
      clearAuthOnUnauthorized: false,
      skipAuthRefresh: true,
    }),

  acceptInvitation: (invitationToken) =>
    api.post("/teachers/accounts/me/invitations/accept", {
      invitation_token: invitationToken,
    }),

  getTeachers: (options = {}) =>
    api.get(`/tenant-admin/teachers?${buildTeacherQuery(options)}`),

  createTeacher: (payload) =>
    api.post("/tenant-admin/teachers", payload),

  createInvitation: (payload) =>
    api.post("/teachers/invitations", payload),

  listInvitations: (options = {}) =>
    api.get(`/teachers/invitations?${buildInvitationQuery(options)}`),

  revokeInvitation: (invitationId) =>
    api.post(`/teachers/invitations/${invitationId}/revoke`),

  listMemberships: (options = {}) =>
    api.get(`/teachers/memberships?${buildTeacherQuery(options)}`),

  getMembership: (membershipId) =>
    api.get(`/teachers/memberships/${membershipId}`),

  updateMembership: (membershipId, payload) =>
    api.patch(`/teachers/memberships/${membershipId}`, payload),

  suspendMembership: (membershipId, reason) =>
    api.post(`/teachers/memberships/${membershipId}/suspend`, { reason }),

  endMembership: (membershipId, reason) =>
    api.post(`/teachers/memberships/${membershipId}/end`, { reason }),

  reactivateMembership: (membershipId, reason) =>
    api.post(`/teachers/memberships/${membershipId}/reactivate`, { reason }),

  replaceSubjectCapabilities: (membershipId, subjectIds) =>
    api.put(`/teachers/memberships/${membershipId}/subject-capabilities`, {
      subject_ids: subjectIds,
    }),

  getMyTeacher: (requestOptions) =>
    api.get("/teachers/me", requestOptions),

  getMySubjects: (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    return api.get(
      `/teachers/me/subjects?${new URLSearchParams({
        skip: String(queryOptions.skip ?? 0),
        limit: String(clampLimit(queryOptions.limit)),
        ...(queryOptions.search ? { search: queryOptions.search } : {}),
        ...(typeof queryOptions.isActive === "boolean"
          ? { is_active: String(queryOptions.isActive) }
          : {}),
      }).toString()}`,
      {
        ...requestOptions,
        ...(signal ? { signal } : {}),
      }
    );
  },

  getTeacher: (teacherId) =>
    api.get(`/tenant-admin/teachers/${teacherId}`),

  updateTeacher: (teacherId, payload) =>
    api.patch(`/tenant-admin/teachers/${teacherId}`, payload),

  updateMyTeacherProfile: (payload) =>
    api.patch("/teachers/me/profile", payload),

  deleteTeacher: (teacherId) =>
    api.delete(`/tenant-admin/teachers/${teacherId}`),
};
