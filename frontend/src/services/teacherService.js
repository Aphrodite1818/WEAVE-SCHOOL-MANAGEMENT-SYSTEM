import { API_BASE_URL, api, authSession } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 50, 1), 100);

const normalizeTeacherMembershipStatus = (status) =>
  status === "ended" ? "inactive" : status;

const buildTeacherQuery = ({ skip = 0, limit = 50, search, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  if (status) params.set("status", normalizeTeacherMembershipStatus(status));
  return params.toString();
};

const buildInvitationQuery = ({ skip = 0, limit = 50, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
  if (status) params.set("status", status);
  return params.toString();
};

const createResponseError = async (response) => {
  const data = await response.json().catch(() => ({}));
  const error = new Error(data?.detail || data?.message || "Request failed.");
  error.response = {
    status: response.status,
    data,
    headers: Object.fromEntries(response.headers.entries()),
  };
  return error;
};

const putJson = async (endpoint, payload, hasRetried = false) => {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "PUT",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(authSession.getToken()
        ? { Authorization: `Bearer ${authSession.getToken()}` }
        : {}),
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 401 && !hasRetried) {
    await api.get("/auth/me/session");
    return putJson(endpoint, payload, true);
  }

  if (!response.ok) throw await createResponseError(response);
  return response.json().catch(() => ({}));
};

const subjectsFromAssignments = (assignments = []) => [
  ...new Map(
    assignments
      .filter((item) => item.subject_id || item.subject_name || item.subject_code)
      .map((item) => [
        item.subject_id || item.subject_name || item.subject_code,
        {
          id: item.subject_id || item.subject_name || item.subject_code,
          name: item.subject_name,
          code: item.subject_code,
          is_active: item.is_active,
        },
      ]),
  ).values(),
];

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

  getInvitationContext: (token) =>
    api.get(`/teachers/invitations/context?token=${encodeURIComponent(token)}`, {
      auth: false,
      clearAuthOnUnauthorized: false,
      skipAuthRefresh: true,
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

  getOffboardingImpact: (membershipId) =>
    api.get(`/teachers/memberships/${membershipId}/offboarding-impact`),

  endMembership: (membershipId, reason, replacementTeacherMembershipId = null) =>
    api.post(`/teachers/memberships/${membershipId}/end`, {
      reason,
      replacement_teacher_membership_id: replacementTeacherMembershipId || null,
    }),

  reactivateMembership: (membershipId, reason) =>
    api.post(`/teachers/memberships/${membershipId}/reactivate`, { reason }),

  listSubjectCapabilities: (membershipId) =>
    api.get(`/teachers/memberships/${membershipId}/subject-capabilities`),

  replaceSubjectCapabilities: (membershipId, subjectIds) =>
    putJson(`/teachers/memberships/${membershipId}/subject-capabilities`, {
      subject_ids: subjectIds,
    }),

  getMyTeacher: (requestOptions) =>
    api.get("/teachers/me", requestOptions),

  getMySubjects: async (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    const response = await api.get("/teachers/academics/assignments", {
      ...requestOptions,
      ...(signal ? { signal } : {}),
    });
    let items = subjectsFromAssignments(response?.items || []);
    if (typeof queryOptions.isActive === "boolean") {
      items = items.filter((item) => item.is_active !== !queryOptions.isActive);
    }
    if (queryOptions.search) {
      const term = String(queryOptions.search).trim().toLowerCase();
      items = items.filter((item) =>
        [item.name, item.code].some((value) =>
          String(value || "").toLowerCase().includes(term),
        ),
      );
    }
    const skip = Number(queryOptions.skip ?? 0) || 0;
    const limit = clampLimit(queryOptions.limit);
    return {
      items: items.slice(skip, skip + limit),
      total: items.length,
    };
  },

  getTeacher: (teacherId) =>
    api.get(`/tenant-admin/teachers/${teacherId}`),

  updateTeacher: (teacherId, payload) =>
    api.patch(`/tenant-admin/teachers/${teacherId}`, payload),

  updateMyTeacherProfile: (payload) =>
    api.patch("/teachers/accounts/me/profile", payload),

  deleteTeacher: (teacherId) =>
    api.delete(`/tenant-admin/teachers/${teacherId}`),
};
